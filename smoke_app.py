"""Smoke test of app.py WITHOUT Streamlit installed: a tiny fake `streamlit` module records widget calls,
and we replay the whole user journey (upload -> analyse -> match -> DOCX -> ZIP -> previews) in both languages.

    python tests/smoke_app.py  [sample_data_dir]
"""
from __future__ import annotations

import io
import runpy
import sys
import types
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))


class SessionState(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError as e:
            raise AttributeError(k) from e

    def __setattr__(self, k, v):
        self[k] = v


class Upload(io.BytesIO):
    def __init__(self, path: Path):
        super().__init__(path.read_bytes())
        self.name, self.size = path.name, path.stat().st_size


class Bar:
    def progress(self, *a, **k):
        return self

    def empty(self):
        pass


class Ctx:
    def __init__(self, st):
        self._st = st

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def update(self, **k):
        self._st.events.append(("status", k))

    def __getattr__(self, name):
        return getattr(self._st, name)


class FakeStreamlit(types.ModuleType):
    def __init__(self):
        super().__init__("streamlit")
        self.session_state = SessionState()
        self.secrets = {}
        self.events: list = []
        self.clicked: set[str] = set()
        self.uploads: dict[str, list[Path]] = {}
        self.choices: dict[str, object] = {}
        self.sidebar = Ctx(self)
        self.column_config = types.SimpleNamespace(**{
            n: (lambda *a, **k: ("col", n, a, k)) for n in ("CheckboxColumn", "TextColumn", "NumberColumn", "SelectboxColumn")})

    # ---- layout
    def set_page_config(self, **k): pass
    def tabs(self, labels): return [Ctx(self) for _ in labels]
    def columns(self, spec):
        n = spec if isinstance(spec, int) else len(spec)
        return [Ctx(self) for _ in range(n)]
    def expander(self, *a, **k): return Ctx(self)
    def spinner(self, *a, **k): return Ctx(self)
    def status(self, *a, **k): return Ctx(self)
    def container(self, *a, **k): return Ctx(self)

    # ---- text
    def _rec(self, kind, *a, **k): self.events.append((kind, a[0] if a else None))
    def title(self, *a, **k): self._rec("title", *a)
    def header(self, *a, **k): self._rec("header", *a)
    def subheader(self, *a, **k): self._rec("subheader", *a)
    def markdown(self, *a, **k): self._rec("markdown", *a)
    def write(self, *a, **k): self._rec("write", *a)
    def caption(self, *a, **k): self._rec("caption", *a)
    def divider(self): pass
    def info(self, *a, **k): self._rec("info", *a)
    def success(self, *a, **k): self._rec("success", *a)
    def warning(self, *a, **k): self._rec("warning", *a)
    def error(self, *a, **k): self._rec("error", *a)
    def metric(self, *a, **k): self._rec("metric", *a)
    def dataframe(self, df, **k): self.events.append(("dataframe", df))
    def image(self, data, **k): self.events.append(("image", len(data)))
    def progress(self, *a, **k): return Bar()
    def rerun(self): self.events.append(("rerun", None))

    # ---- widgets
    def _val(self, key, default):
        return self.choices.get(key, self.session_state.get(key, default))

    def radio(self, label, options, key=None, **k):
        v = self._val(key, options[0]); self.session_state[key] = v; return v
    def toggle(self, label, value=False, key=None, **k):
        v = self._val(key, value); self.session_state[key] = v; return v
    checkbox = toggle
    def slider(self, label, lo, hi, value, step=None, key=None, **k):
        v = self._val(key, value); self.session_state[key] = v; return v
    def selectbox(self, label, options, key=None, **k):
        options = list(options)
        v = self._val(key, options[0] if options else None)
        if v not in options and options:
            v = options[0]
        self.session_state[key] = v; return v
    def multiselect(self, label, options, default=None, key=None, **k):
        v = self._val(key, list(default or [])); self.session_state[key] = v; return v
    def text_input(self, label, value="", key=None, **k):
        v = self._val(key, value); self.session_state[key] = v; return v
    def file_uploader(self, label, key=None, **k):
        return [Upload(p) for p in self.uploads.get(key, [])]
    def button(self, label, key=None, disabled=False, **k):
        return (key in self.clicked) and not disabled
    def data_editor(self, df, **k): return df.copy()
    def download_button(self, label, data=None, file_name=None, key=None, **k):
        blob = data() if callable(data) else data
        self.events.append(("download", key, file_name, len(blob)))
        self.session_state[f"_dl_{key}"] = blob
    def stop(self): raise SystemExit


def run(fake: FakeStreamlit, clicked=(), **choices):
    fake.clicked, fake.choices = set(clicked), choices
    fake.events.clear()
    sys.modules["streamlit"] = fake
    runpy.run_path(str(ROOT / "app.py"), run_name="__main__")
    return list(fake.events)


def main(sample: Path) -> None:
    import make_sample_data
    if not (sample / "tender").exists():
        make_sample_data.build(sample)
    fake = FakeStreamlit()
    fake.uploads = {
        "tender_uploader": [sample / "tender" / "Tender_Package.zip"],
        "bidder_uploader": sorted((sample / "bidders").glob("*.zip")),
    }
    for lang in ("English", "हिन्दी"):
        ev = run(fake, lang_choice=lang)
        assert any(e[0] == "title" for e in ev)
    print("1 initial render ok (both languages)")

    ev = run(fake, ["btn_tender_save"], lang_choice="हिन्दी")
    assert fake.session_state.tender_set and len(fake.session_state.tender_set.files) == 3
    print("2 tender saved:", [f.rel for f in fake.session_state.tender_set.files])

    run(fake, ["btn_bidder_save"], lang_choice="हिन्दी")
    assert len(fake.session_state.bidder_set.bidders) == 3
    print("3 bidders:", list(fake.session_state.bidder_set.bidders))

    ev = run(fake, ["btn_analyze"], lang_choice="हिन्दी")
    n = len(fake.session_state.analysis.reqs)
    assert n >= 20 and fake.session_state.reqs_df is not None
    print("4 requirements found:", n)

    ev = run(fake, ["btn_match"], lang_choice="हिन्दी")
    res = fake.session_state.match
    assert res is not None and any(e[0] == "markdown" and "tm-wrap" in str(e[1]) for e in ev)
    print("5 matched; statuses of bidder 1:", res.counts(res.bidders[0]))

    ev = run(fake, ["btn_docx"], lang_choice="English")
    assert any(e[0] == "download" and e[1] == "dl_docx" for e in ev)
    print("6 docx download offered:", [e for e in ev if e[0] == "download"])

    ev = run(fake, ["btn_prev_docx"], lang_choice="English")
    assert any(e[0] == "image" for e in ev), "docx page preview"
    print("7 docx preview images:", sum(1 for e in ev if e[0] == "image"))

    ev = run(fake, ["btn_zip"], lang_choice="English")
    assert any(e[0] == "download" and e[1] == "dl_zip" for e in ev)
    print("8 zip offered:", [e for e in ev if e[0] == "download" and e[1] == "dl_zip"])

    ev = run(fake, ["btn_prev_pdf"], lang_choice="English")
    assert any(e[0] == "image" for e in ev), "pdf preview"
    print("9 pdf preview ok")

    # manual correction path
    rid = fake.session_state.match_reqs[-1].rid
    b = fake.session_state.match.bidders[0]
    rel = next(rel for (bb, rel) in fake.session_state.match.paths if bb == b)
    ev = run(fake, ["man_apply"], man_b=b, man_r=rid, **{f"man_f_{b}_{rid}_{len(fake.session_state.match.cells.get((rid, b), []))}": [rel]})
    assert fake.session_state.match.status(rid, b) == "Submitted"
    print("10 manual correction ok")

    ev = run(fake, ["btn_reset"])
    print("smoke test passed")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/sample"))
