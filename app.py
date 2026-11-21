"""Tender Matrix  |  टेंडर मैट्रिक्स
Wanting-document matrix & bidder technical-evaluation helper (English + Hindi).

Run locally:   streamlit run app.py
"""
from __future__ import annotations

import io
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from tendermatrix import __version__
from tendermatrix.bidders import rename_bidders, unpack_bidders, unpack_tender
from tendermatrix.docx_report import build_matrix_docx
from tendermatrix.extract import tesseract_available
from tendermatrix.i18n import tr
from tendermatrix.llm import DEFAULT_MODEL
from tendermatrix.matching import build_vocab, compile_specs, match_all, refeat
from tendermatrix.models import MANDATORY, OPTIONAL, df_to_reqs, reqs_to_df
from tendermatrix.office import find_soffice
from tendermatrix.package_zip import build_output_zip
from tendermatrix.pipeline import analyze_tender, index_bidder_set
from tendermatrix.preview import docx_preview_images, matrix_df, matrix_html, render_pdf_pages
from tendermatrix.utils import human_size, new_workspace, remove_tree, save_upload

MAX_MB = 500
MB = 1024 * 1024
UP_TYPES = ["pdf", "docx", "doc", "xlsx", "xls", "zip"]

st.set_page_config(page_title="Tender Matrix | टेंडर मैट्रिक्स", page_icon="📑", layout="wide")
SS = st.session_state

# ----------------------------------------------------------------------------- state
_DEFAULTS = dict(
    tender_ws=None, tender_set=None, tender_ver=0,
    bidder_ws=None, bidder_set=None, bidder_ver=0, bidder_names={},
    analysis=None, reqs_df=None, reqs_edit=None, reqs_ver=0,
    feats=None, feats_sig=None, match=None, match_reqs=None,
    docx_bytes=None, docx_prev=None, out_ws=None, zip_path=None, zip_entries=None,
)
for _k, _v in _DEFAULTS.items():
    SS.setdefault(_k, _v)


def clear_outputs() -> None:
    SS.docx_bytes = SS.docx_prev = SS.zip_entries = None
    if SS.out_ws:
        remove_tree(SS.out_ws)
    SS.out_ws = SS.zip_path = None


def reset_after_tender() -> None:
    SS.analysis = SS.reqs_df = SS.reqs_edit = SS.match = SS.match_reqs = None
    SS.reqs_ver += 1
    clear_outputs()


def reset_after_bidders() -> None:
    SS.feats = SS.feats_sig = SS.match = SS.match_reqs = None
    SS.bidder_names = {}
    clear_outputs()


def reset_all() -> None:
    for ws in (SS.tender_ws, SS.bidder_ws, SS.out_ws):
        remove_tree(ws)
    for k, v in _DEFAULTS.items():
        SS[k] = v
    SS.tender_ver += 1
    SS.bidder_ver += 1


def _secret_key() -> str:
    try:
        return str(st.secrets.get("ANTHROPIC_API_KEY", "") or "")
    except Exception:
        return ""


# ---------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.radio("Language / भाषा", ["English", "हिन्दी"], key="lang_choice", horizontal=True)
L = "hi" if SS.get("lang_choice") == "हिन्दी" else "en"


def t(key: str, **kw) -> str:
    return tr(L, key, **kw)


with st.sidebar:
    st.header(t("settings"))
    use_ai = st.toggle(t("use_ai"), value=False, key="use_ai", help=t("use_ai_help"))
    api_key, model = "", DEFAULT_MODEL
    if use_ai:
        api_key = _secret_key()
        if api_key:
            st.caption(t("key_from_secrets"))
        else:
            api_key = st.text_input(t("api_key"), type="password", key="api_key_in")
        model = st.text_input(t("model"), value=DEFAULT_MODEL, key="model_in") or DEFAULT_MODEL
        if not api_key:
            st.warning(t("no_key"))
    ocr_ok = tesseract_available()
    use_ocr = st.checkbox(t("use_ocr"), value=False, disabled=not ocr_ok, key="use_ocr", help=t("use_ocr_help"))
    threshold = st.slider(t("threshold"), 0.40, 0.95, 0.60, 0.05, key="thr", help=t("threshold_help"))
    name_lang = st.selectbox(t("name_lang"), ["both", "en", "hi"], format_func=lambda k: t(f"lang_{k}"), key="name_lang",
                             help=t("name_lang_help"))
    doc_lang = st.selectbox(t("doc_lang"), ["both", "en", "hi"], format_func=lambda k: t(f"lang_{k}"), key="doc_lang")
    annex_a = st.checkbox(t("annex_a"), value=True, key="annex_a")
    annex_b = st.checkbox(t("annex_b"), value=True, key="annex_b")
    zip_extras = st.checkbox(t("zip_extras"), value=True, key="zip_extras")
    st.divider()
    st.caption(("✅ " if find_soffice() else "⚠️ ") + t("st_libre" if find_soffice() else "st_libre_missing"))
    st.caption(("✅ " if ocr_ok else "⚠️ ") + t("st_ocr" if ocr_ok else "st_ocr_missing"))
    st.button(t("reset_all"), on_click=reset_all, key="btn_reset")
    st.caption(f"v{__version__}")

# ----------------------------------------------------------------------------- header
st.title("📑 " + t("app_title"))
st.caption(t("app_sub"))

tab1, tab2, tab3, tab4 = st.tabs([t("tab1"), t("tab2"), t("tab3"), t("tab4")])


def uploader(key: str, label: str):
    files = st.file_uploader(label, type=UP_TYPES, accept_multiple_files=True, key=key, help=t("upload_help", mb=MAX_MB))
    total = sum(f.size for f in files) if files else 0
    st.progress(min(total / (MAX_MB * MB), 1.0), text=t("upload_size", used=human_size(total), mb=MAX_MB))
    over = total > MAX_MB * MB
    if over:
        st.error(t("upload_too_big", mb=MAX_MB))
    return files, over


def save_all(files, ws: Path) -> list[Path]:
    bar = st.progress(0.0, text=t("saving"))
    saved = []
    for i, f in enumerate(files):
        saved.append(save_upload(f, ws / "uploads"))
        bar.progress((i + 1) / len(files), text=f"{t('saving')} {i + 1}/{len(files)}")
    bar.empty()
    return saved


# ======================================================================== TAB 1: tender
with tab1:
    st.subheader(t("t1_head"))
    st.write(t("t1_help"))
    st.text_input(t("tender_title"), key="tender_title", placeholder=t("tender_title_ph"))
    t_files, t_over = uploader("tender_uploader", t("t1_upload"))
    if st.button(t("btn_read"), type="primary", disabled=not t_files or t_over, key="btn_tender_save"):
        with st.status(t("processing"), expanded=True) as stt:
            remove_tree(SS.tender_ws)
            SS.tender_ws = new_workspace("tender")
            saved = save_all(t_files, SS.tender_ws)
            SS.tender_set = unpack_tender(saved, SS.tender_ws / "files")
            SS.tender_ver += 1
            reset_after_tender()
            stt.update(label=t("t1_done", n=len(SS.tender_set.files)), state="complete")

    ts = SS.tender_set
    if ts is not None:
        for w in ts.warnings:
            st.warning(w)
        if ts.unsupported:
            st.info(t("unsupported", files=", ".join(ts.unsupported[:15])))
        if not ts.files:
            st.error(t("no_files"))
        else:
            st.markdown(f"**{t('t1_files')}** ({len(ts.files)})")
            st.caption(t("t1_corr_help"))
            df = pd.DataFrame({
                "corrigendum": [f.corrigendum for f in ts.files],
                "file": [f.rel for f in ts.files],
                "size": [human_size(f.size) for f in ts.files],
            })
            edited = st.data_editor(
                df, key=f"tender_tbl_{SS.tender_ver}", hide_index=True, disabled=["file", "size"],
                column_config={
                    "corrigendum": st.column_config.CheckboxColumn(t("col_corr")),
                    "file": st.column_config.TextColumn(t("col_file"), width="large"),
                    "size": st.column_config.TextColumn(t("col_size")),
                },
            )
            for f, c in zip(ts.files, edited["corrigendum"]):
                f.corrigendum = bool(c)
            st.success(t("t1_next"))

# ====================================================================== TAB 2: bidders
with tab2:
    st.subheader(t("t2_head"))
    st.write(t("t2_help"))
    mode = st.selectbox(
        t("t2_mode"), ["auto", "zip_per_bidder", "folder_per_bidder"], format_func=lambda m: t(f"mode_{m}"),
        key="bidder_mode", help=t("t2_mode_help"),
    )
    b_files, b_over = uploader("bidder_uploader", t("t2_upload"))
    if st.button(t("btn_detect"), type="primary", disabled=not b_files or b_over, key="btn_bidder_save"):
        with st.status(t("processing"), expanded=True) as stt:
            remove_tree(SS.bidder_ws)
            SS.bidder_ws = new_workspace("bidders")
            saved = save_all(b_files, SS.bidder_ws)
            st.write(t("unzipping"))
            SS.bidder_set = unpack_bidders(saved, SS.bidder_ws / "files", mode)
            SS.bidder_ver += 1
            reset_after_bidders()
            stt.update(label=t("t2_done", n=len(SS.bidder_set.bidders)), state="complete")

    bs = SS.bidder_set
    if bs is not None:
        for w in bs.warnings[:20]:
            st.warning(w)
        if not bs.bidders:
            st.error(t("no_files"))
        else:
            st.markdown(f"**{t('t2_list')}** ({len(bs.bidders)})")
            st.caption(t("t2_rename_help"))
            rows = []
            for name, files in bs.bidders.items():
                rows.append({"name": name, "files": len(files), "size": human_size(sum(f.stat().st_size for f in files)),
                             "how": bs.modes.get(name, ""), "_old": name})
            bdf = pd.DataFrame(rows)
            bedit = st.data_editor(
                bdf, key=f"bidder_tbl_{SS.bidder_ver}", hide_index=True, disabled=["files", "size", "how"],
                column_order=["name", "files", "size", "how"],
                column_config={
                    "name": st.column_config.TextColumn(t("col_bidder"), width="large", required=True),
                    "files": st.column_config.NumberColumn(t("col_nfiles")),
                    "size": st.column_config.TextColumn(t("col_size")),
                    "how": st.column_config.TextColumn(t("col_how")),
                },
            )
            SS.bidder_names = dict(zip(bedit["_old"], bedit["name"]))
            for name, bad in bs.unsupported.items():
                st.info(t("unsupported_b", name=name, files=", ".join(bad[:10])))
            with st.expander(t("t2_view_files")):
                pick = st.selectbox(t("col_bidder"), list(bs.bidders), key="view_bidder")
                root = bs.roots[pick]
                st.dataframe(pd.DataFrame({
                    "file": [f.relative_to(root).as_posix() for f in bs.bidders[pick][:500]],
                    "size": [human_size(f.stat().st_size) for f in bs.bidders[pick][:500]],
                }), hide_index=True)
            st.success(t("t2_next"))

# ======================================================================= TAB 3: analysis
with tab3:
    st.subheader(t("t3_head"))
    st.markdown("#### " + t("t3_step_a"))
    if SS.tender_set is None or not SS.tender_set.files:
        st.info(t("need_tender"))
    c1, c2 = st.columns([1, 3])
    run_a = c1.button(t("btn_analyze"), type="primary", disabled=not (SS.tender_set and SS.tender_set.files), key="btn_analyze")
    c2.caption(t("analysis_mode_ai") if (use_ai and api_key) else t("analysis_mode_rules"))
    if run_a:
        bar = st.progress(0.0, text=t("analyzing"))
        out = analyze_tender(
            SS.tender_set.files, use_ai=bool(use_ai and api_key), api_key=api_key, model=model, ocr=use_ocr,
            name_lang=name_lang, ui_lang=L, progress=lambda p, m: bar.progress(min(max(p, 0.0), 1.0), text=m),
        )
        bar.empty()
        SS.analysis = out
        SS.reqs_df = reqs_to_df(out.reqs)
        SS.reqs_ver += 1
        SS.match = SS.match_reqs = None
        clear_outputs()

    out = SS.analysis
    if out is not None:
        for w in out.warnings:
            st.warning(w)
        for w in out.unreadable[:10]:
            st.warning(w)
        n_inc = int(SS.reqs_df["include"].sum()) if SS.reqs_df is not None and len(SS.reqs_df) else 0
        m1, m2, m3 = st.columns(3)
        m1.metric(t("m_found"), len(out.reqs))
        m2.metric(t("m_included"), n_inc)
        m3.metric(t("m_mode"), "AI" if out.mode == "ai" else t("m_rules"))
        if not out.reqs:
            st.error(t("none_found"))
        st.caption(t("t3_edit_help"))
        edited = st.data_editor(
            SS.reqs_df, key=f"reqs_tbl_{SS.reqs_ver}", num_rows="dynamic", hide_index=True,
            column_order=["include", "name", "mandatory", "category", "source", "confidence", "reference", "keywords"],
            column_config={
                "include": st.column_config.CheckboxColumn(t("col_include"), default=True),
                "name": st.column_config.TextColumn(t("col_doc"), width="large", required=True),
                "mandatory": st.column_config.SelectboxColumn(t("col_type"), options=[MANDATORY, OPTIONAL],
                                                               default=MANDATORY, required=True),
                "category": st.column_config.TextColumn(t("col_cat")),
                "source": st.column_config.TextColumn(t("col_source"), disabled=True),
                "confidence": st.column_config.TextColumn(t("col_conf"), disabled=True),
                "reference": st.column_config.TextColumn(t("col_ref"), width="large"),
                "keywords": st.column_config.TextColumn(t("col_kw"), width="large", help=t("col_kw_help")),
            },
        )
        SS.reqs_edit = edited

    # ---------------------------------------------------------------- step B
    st.divider()
    st.markdown("#### " + t("t3_step_b"))
    have_reqs = SS.reqs_edit is not None and len(df_to_reqs(SS.reqs_edit)) > 0
    have_bid = SS.bidder_set is not None and bool(SS.bidder_set.bidders)
    if not have_bid:
        st.info(t("need_bidders"))
    if not have_reqs:
        st.info(t("need_list"))
    run_b = st.button(t("btn_match"), type="primary", disabled=not (have_reqs and have_bid), key="btn_match")
    if run_b:
        reqs = df_to_reqs(SS.reqs_edit)
        bs0 = SS.bidder_set
        bs2 = rename_bidders(bs0, SS.bidder_names or {})
        specs = compile_specs(reqs)
        vocab = build_vocab(specs)
        bar = st.progress(0.0, text=t("indexing"))
        sig = (SS.bidder_ver, bool(use_ocr))
        if SS.feats is None or SS.feats_sig != sig:
            SS.feats = index_bidder_set(bs0, vocab, bool(use_ocr),
                                        progress=lambda p, m: bar.progress(min(max(p, 0.0), 1.0), text=f"{t('indexing')} {m}"[:150]))
            SS.feats_sig = sig
        else:
            refeat(SS.feats, vocab)
        feats_r = {new: SS.feats[old] for old, new in zip(bs0.bidders, bs2.bidders)}
        bar.progress(0.97, text=t("matching"))
        SS.match = match_all(feats_r, specs, threshold)
        SS.match_reqs = reqs
        bar.empty()
        clear_outputs()

    res, mreqs = SS.match, SS.match_reqs
    if res is not None and mreqs:
        st.markdown("##### " + t("t3_matrix"))
        st.markdown(matrix_html(mreqs, res, L), unsafe_allow_html=True)
        with st.expander("📋 " + t("table_view")):
            st.dataframe(matrix_df(mreqs, res), hide_index=True)
        summ = []
        for b in res.bidders:
            s, n, mm = res.counts(b)
            summ.append({t("col_bidder"): b, "Submitted": s, "Not Submitted": n, t("col_mand_missing"): mm})
        st.dataframe(pd.DataFrame(summ), hide_index=True)

        with st.expander("✏️ " + t("manual_title")):
            st.caption(t("manual_help"))
            idx = {r.rid: f"{i}. {r.name[:90]}" for i, r in enumerate(mreqs, 1)}
            mb = st.selectbox(t("col_bidder"), res.bidders, key="man_b")
            mr = st.selectbox(t("col_doc"), list(idx), format_func=lambda k: idx[k], key="man_r")
            all_rels = sorted(rel for (bb, rel) in res.paths if bb == mb)
            cur = [m.rel for m in res.cells.get((mr, mb), [])]
            sel = st.multiselect(t("manual_files"), all_rels, default=cur, key=f"man_f_{mb}_{mr}_{len(cur)}")
            if st.button(t("manual_apply"), key="man_apply"):
                res.set_manual(mr, mb, sel)
                clear_outputs()
                st.rerun()

        with st.expander("🔎 " + t("cands_title")):
            st.caption(t("cands_help"))
            rows = []
            for (rid, b), ms in res.cands.items():
                if res.cells.get((rid, b)):
                    continue
                nm = next((r.name for r in mreqs if r.rid == rid), rid)
                for m in ms:
                    rows.append({t("col_bidder"): b, t("col_doc"): nm[:80], t("col_file"): m.rel, "score": m.score, "basis": m.how})
            if rows:
                st.dataframe(pd.DataFrame(rows[:400]), hide_index=True)
            else:
                st.write(t("none"))

        with st.expander("📂 " + t("unmatched_title")):
            for b in res.bidders:
                un = res.unmatched.get(b, [])
                unr = res.unreadable.get(b, [])
                st.markdown(f"**{b}** - {len(un)} {t('unmatched_n')}, {len(unr)} {t('unreadable_n')}")
                if un:
                    st.caption(" • ".join(un[:60]) + (" ..." if len(un) > 60 else ""))

# ======================================================================= TAB 4: outputs
with tab4:
    st.subheader(t("t4_head"))
    res, mreqs = SS.match, SS.match_reqs
    if res is None or not mreqs:
        st.info(t("need_match"))
    else:
        # ---------------------------------------------------------- DOCX
        st.markdown("#### 1️⃣ " + t("t4_docx"))
        if st.button(t("btn_build_docx"), type="primary", key="btn_docx"):
            with st.spinner(t("building")):
                SS.docx_bytes = build_matrix_docx(
                    mreqs, res, tender_title=SS.get("tender_title", ""), lang=doc_lang,
                    include_annex_a=annex_a, include_annex_b=annex_b,
                )
                SS.docx_prev = None
        if SS.docx_bytes:
            fname = f"Wanting_Document_Matrix_{datetime.now():%Y%m%d_%H%M}.docx"
            st.download_button(
                "⬇️ " + t("dl_docx"), data=SS.docx_bytes, file_name=fname, key="dl_docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
            if st.button(t("btn_prev_docx"), key="btn_prev_docx"):
                with st.spinner(t("building")):
                    SS.docx_prev = docx_preview_images(SS.docx_bytes, count=4) or "none"
            if SS.docx_prev == "none":
                st.info(t("no_libre_preview"))
            elif SS.docx_prev:
                imgs, total = SS.docx_prev
                st.caption(t("pages_shown", n=len(imgs), total=total))
                for im in imgs:
                    st.image(im, width="stretch")

        # ---------------------------------------------------------- ZIP
        st.divider()
        st.markdown("#### 2️⃣ " + t("t4_zip"))
        st.caption(t("t4_zip_help"))
        n_sub = sum(1 for k, v in res.cells.items() if v)
        if st.button(t("btn_build_zip"), type="primary", disabled=n_sub == 0, key="btn_zip"):
            if SS.out_ws is None:
                SS.out_ws = new_workspace("out")
            extras = {}
            if zip_extras:
                if SS.docx_bytes is None:
                    SS.docx_bytes = build_matrix_docx(mreqs, res, tender_title=SS.get("tender_title", ""), lang=doc_lang,
                                                      include_annex_a=annex_a, include_annex_b=annex_b)
                extras["00_Wanting_Document_Matrix.docx"] = SS.docx_bytes
            bar = st.progress(0.0, text=t("building"))
            zpath = Path(SS.out_ws) / "Submitted_Documents.zip"
            SS.zip_entries = build_output_zip(
                mreqs, res, zpath, Path(SS.out_ws), extras=extras,
                progress=lambda p, m: bar.progress(min(max(p, 0.0), 1.0), text=m),
            )
            SS.zip_path = str(zpath)
            bar.empty()
        if SS.zip_path and Path(SS.zip_path).exists():
            zp = Path(SS.zip_path)
            st.success(t("zip_ready", n=len(SS.zip_entries), size=human_size(zp.stat().st_size)))
            zname = f"Submitted_Documents_{datetime.now():%Y%m%d_%H%M}.zip"

            def _zip_bytes() -> bytes:
                return zp.read_bytes()

            try:
                st.download_button("⬇️ " + t("dl_zip"), data=_zip_bytes, file_name=zname, mime="application/zip",
                                   key="dl_zip", on_click="ignore")
            except Exception:  # older Streamlit without deferred data
                st.download_button("⬇️ " + t("dl_zip"), data=zp.read_bytes(), file_name=zname, mime="application/zip", key="dl_zip_b")

            ent = pd.DataFrame([{
                t("col_bidder"): e["bidder"], "#": e["idx"], t("col_doc"): e["req"][:70],
                t("col_orig"): e["rel"], t("col_inzip"): e.get("arc", ""), t("col_conv"): e.get("method", ""),
                t("col_note"): e.get("note", ""),
            } for e in SS.zip_entries])
            st.markdown("##### " + t("zip_contents"))
            st.dataframe(ent, hide_index=True)
            bad = [e for e in SS.zip_entries if e.get("note")]
            if bad:
                st.warning(t("zip_notes", n=len(bad)))

            st.markdown("##### " + t("zip_preview"))
            arcs = [e["arc"] for e in SS.zip_entries if e.get("arc", "").lower().endswith(".pdf")]
            if arcs:
                pick = st.selectbox(t("zip_pick"), arcs, key="zip_pick")
                npg = st.slider(t("pages_to_show"), 1, 5, 2, key="zip_pages")
                if st.button(t("btn_preview_pdf"), key="btn_prev_pdf"):
                    try:
                        with zipfile.ZipFile(zp) as zf:
                            data = zf.read(pick)
                        imgs, total = render_pdf_pages(data, 0, npg)
                        st.caption(t("pages_shown", n=len(imgs), total=total))
                        for im in imgs:
                            st.image(im, width="stretch")
                    except Exception as ex:
                        st.error(f"{type(ex).__name__}: {ex}")

st.divider()
with st.expander("ℹ️ " + t("notes_title")):
    st.markdown(t("notes_body", mb=MAX_MB))
