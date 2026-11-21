"""UI strings - English and Hindi (Devanagari)."""
from __future__ import annotations

STR: dict[str, dict[str, str]] = {
    "en": {
        "app_title": "Tender Matrix - Wanting Document List & Bidder Evaluation",
        "app_sub": "Upload tender + corrigendum and bidders' technical documents. The app prepares the wanting-document matrix "
                   "(DOCX), marks every bidder Submitted / Not Submitted and packs the submitted documents as separate PDFs in one ZIP.",
        "tab1": "1️⃣ Tender / Bid data", "tab2": "2️⃣ Bidders data", "tab3": "3️⃣ Analysis & Matrix", "tab4": "4️⃣ Download & Preview",
        # sidebar
        "settings": "Settings",
        "use_ai": "AI mode (Claude)", "use_ai_help": "Better tender reading, esp. for long / complex tenders. Needs an Anthropic API key. "
                                                      "Without it the free offline rules are used.",
        "api_key": "Anthropic API key", "model": "Model", "key_from_secrets": "API key found in app secrets.",
        "no_key": "No API key - offline rules will be used.",
        "use_ocr": "OCR for scanned PDFs / images", "use_ocr_help": "Reads text inside scanned documents (English + Hindi). Slower.",
        "threshold": "Match strictness", "threshold_help": "Higher = stricter. 0.60 is a good default. Lower it to also accept generic matches "
                                                          "(e.g. a file just called 'Declaration').",
        "name_lang": "Document names (new list)", "name_lang_help": "Language of the document names when the wanting list is generated.",
        "doc_lang": "DOCX heading language", "lang_both": "English + हिन्दी", "lang_en": "English", "lang_hi": "हिन्दी",
        "annex_a": "DOCX: add Annexure A (tender references)", "annex_b": "DOCX: add Annexure B (file-wise mapping)",
        "zip_extras": "ZIP: also include matrix DOCX", "reset_all": "🗑️ Clear all data",
        "st_libre": "LibreOffice found (best DOCX/XLSX to PDF)", "st_libre_missing": "LibreOffice missing - simple PDF fallback",
        "st_ocr": "OCR available", "st_ocr_missing": "OCR not installed",
        # common
        "saving": "Saving files", "processing": "Processing ...", "unzipping": "Unpacking ZIP files ...", "none": "Nothing to show.",
        "no_files": "No supported files found (PDF, DOCX, XLSX, ZIP).",
        "upload_help": "PDF, DOCX, DOC, XLSX, XLS or ZIP. Up to {mb} MB in total.",
        "upload_size": "{used} of {mb} MB used", "upload_too_big": "Total size is more than {mb} MB. Please upload in two parts.",
        "unsupported": "Skipped unsupported files: {files}", "unsupported_b": "{name}: skipped unsupported files - {files}",
        "col_file": "File", "col_size": "Size", "col_corr": "Corrigendum?", "col_bidder": "Bidder", "col_nfiles": "Files",
        "col_how": "Detected from", "col_include": "Use", "col_doc": "Wanting document", "col_type": "Type", "col_cat": "Category",
        "col_source": "Source", "col_conf": "Confidence", "col_ref": "Tender reference", "col_kw": "Keywords (for matching)",
        "col_kw_help": "Words / phrases (English, Hindi, Hinglish) that appear in the file name or title of the bidder's document. Separate with ; ",
        "col_mand_missing": "Mandatory missing", "col_orig": "Uploaded file", "col_inzip": "File in ZIP", "col_conv": "PDF by", "col_note": "Note",
        # tab 1
        "t1_head": "Tender / Bid documents", "t1_help": "Upload the tender documents and corrigendum / addendum (PDF, DOCX, XLSX or ZIP). "
                                                      "Files with 'corrigendum', 'addendum' or 'शुद्धिपत्र' in the name are detected automatically.",
        "tender_title": "Tender title / number (shown in the DOCX)", "tender_title_ph": "e.g. PWD/ELEC/2026/045 - LED street lights",
        "t1_upload": "Upload tender / bid data", "btn_read": "Save & read tender files",
        "t1_done": "{n} tender file(s) ready", "t1_files": "Tender files", "t1_corr_help": "Tick 'Corrigendum?' for amendment files so they are read as changes.",
        "t1_next": "Next: upload bidders' data in tab 2, then analyse in tab 3.",
        # tab 2
        "t2_head": "Bidders' technical documents",
        "t2_help": "Upload one ZIP per bidder (ZIP name = bidder name) with its PDF / DOCX / XLSX files. A single ZIP with one folder per bidder also works.",
        "t2_mode": "How are bidders organised?", "t2_mode_help": "Auto detects it from the ZIP structure - you can correct the names below.",
        "mode_auto": "Auto detect", "mode_zip_per_bidder": "Each ZIP = one bidder", "mode_folder_per_bidder": "Each folder inside a ZIP = one bidder",
        "t2_upload": "Upload bidders' data", "btn_detect": "Save & detect bidders", "t2_done": "{n} bidder(s) detected",
        "t2_list": "Bidders", "t2_rename_help": "You can edit bidder names - they are used in the matrix and in the ZIP.",
        "t2_view_files": "View files of a bidder", "t2_next": "Next: open tab 3 to create the wanting list and match.",
        # tab 3
        "t3_head": "Analysis & Wanting Document Matrix", "t3_step_a": "Step A - Read the tender and make the wanting document list",
        "need_tender": "First upload and read tender files in tab 1.", "btn_analyze": "Analyse tender",
        "analysis_mode_ai": "AI mode is ON", "analysis_mode_rules": "Offline smart-rules mode (free)", "analyzing": "Analysing tender ...",
        "m_found": "Documents found", "m_included": "Included", "m_mode": "Mode", "m_rules": "Rules", "none_found": "No documents were detected. "
                                                                                                                  "Add rows manually below or try AI mode / OCR.",
        "t3_edit_help": "Check and edit the list: untick a row to drop it, edit names or keywords, add new rows at the bottom. "
                        "Rows from a corrigendum are marked in 'Source'.",
        "t3_step_b": "Step B - Match bidders' documents", "need_bidders": "First upload and detect bidders in tab 2.",
        "need_list": "Create (or add) at least one wanting document in Step A.", "btn_match": "Match bidders' documents",
        "indexing": "Reading bidders' files ...", "matching": "Matching ...", "t3_matrix": "Wanting Document Matrix (preview)",
        "table_view": "Plain table view", "manual_title": "Manual correction", "manual_help": "Pick a bidder and a document, then choose exactly which file(s) satisfy it. "
                                                          "Choosing no file makes it 'Not Submitted'.",
        "manual_files": "Files that satisfy this document", "manual_apply": "Apply",
        "cands_title": "Possible matches below the strictness level", "cands_help": "Files that look related but were not accepted. "
                                                                                    "Use manual correction to accept one.",
        "unmatched_title": "Files not matched to any wanting document", "unmatched_n": "unmatched file(s)", "unreadable_n": "without readable text",
        # tab 4
        "t4_head": "Download & Preview", "need_match": "Run the matching in tab 3 first.",
        "t4_docx": "Wanting Document List / Matrix (DOCX)", "btn_build_docx": "Create / refresh DOCX", "building": "Building ...",
        "dl_docx": "Download matrix (DOCX)", "btn_prev_docx": "Preview DOCX pages", "no_libre_preview": "Page preview needs LibreOffice; see the matrix preview in tab 3.",
        "pages_shown": "Showing {n} of {total} page(s)",
        "t4_zip": "Submitted documents as separate PDFs (ZIP)",
        "t4_zip_help": "Folder per bidder; every file is named  <S.No>_<document>__<original name>.pdf  so it lines up with the matrix.",
        "btn_build_zip": "Create ZIP of submitted documents", "zip_ready": "ZIP ready: {n} PDF file(s), {size}", "dl_zip": "Download ZIP",
        "zip_contents": "ZIP contents", "zip_notes": "{n} file(s) have a note (simplified conversion or conversion failed) - see the table.",
        "zip_preview": "Preview a document from the ZIP", "zip_pick": "Document", "pages_to_show": "Pages to show", "btn_preview_pdf": "Show preview",
        "notes_title": "Notes & limits",
        "notes_body": "- Upload limit: **{mb} MB per tab**. Streamlit Community Cloud has limited RAM (~2.7 GB), so for very large sets upload in parts.\n"
                      "- Matching is automatic (file names, first-page text, keywords). **Always verify** before the final evaluation - use *Manual correction*.\n"
                      "- Scanned PDFs / photos need **OCR** (sidebar). Old Hindi PDFs with legacy fonts (Kruti Dev) may not be readable as text.\n"
                      "- Uploaded data lives only in this session's temporary storage; use *Clear all data* when finished.",
    },
    "hi": {
        "app_title": "टेंडर मैट्रिक्स - वांछित दस्तावेज़ सूची एवं बिडर मूल्यांकन",
        "app_sub": "टेंडर + शुद्धिपत्र और बिडर्स के तकनीकी दस्तावेज़ अपलोड करें। ऐप वांछित दस्तावेज़ मैट्रिक्स (DOCX) बनाएगा, हर बिडर के सामने "
                   "Submitted / Not Submitted लिखेगा और जमा किए गए दस्तावेज़ों को अलग-अलग PDF में एक ZIP में देगा।",
        "tab1": "1️⃣ टेंडर / बिड डेटा", "tab2": "2️⃣ बिडर्स डेटा", "tab3": "3️⃣ विश्लेषण एवं मैट्रिक्स", "tab4": "4️⃣ डाउनलोड एवं प्रीव्यू",
        "settings": "सेटिंग्स",
        "use_ai": "AI मोड (Claude)", "use_ai_help": "लंबे / जटिल टेंडर को बेहतर पढ़ता है। Anthropic API key चाहिए। "
                                                      "बिना key के मुफ़्त ऑफ़लाइन नियम उपयोग होंगे।",
        "api_key": "Anthropic API key", "model": "मॉडल", "key_from_secrets": "ऐप secrets में API key मिल गई।",
        "no_key": "API key नहीं है - ऑफ़लाइन नियम उपयोग होंगे।",
        "use_ocr": "स्कैन PDF / फ़ोटो के लिए OCR", "use_ocr_help": "स्कैन दस्तावेज़ों के अंदर का टेक्स्ट पढ़ता है (अंग्रेज़ी + हिन्दी)। धीमा होता है।",
        "threshold": "मिलान की कठोरता", "threshold_help": "ज़्यादा = ज़्यादा सख़्त। 0.60 उचित है। सामान्य नाम वाली फ़ाइलें "
                                                         "(जैसे केवल 'Declaration') भी मानने के लिए घटाएँ।",
        "name_lang": "दस्तावेज़ नामों की भाषा (नई सूची)", "name_lang_help": "वांछित सूची बनते समय दस्तावेज़ नामों की भाषा।",
        "doc_lang": "DOCX शीर्षकों की भाषा", "lang_both": "English + हिन्दी", "lang_en": "English", "lang_hi": "हिन्दी",
        "annex_a": "DOCX: अनुलग्नक A जोड़ें (निविदा संदर्भ)", "annex_b": "DOCX: अनुलग्नक B जोड़ें (फ़ाइल-वार मिलान)",
        "zip_extras": "ZIP में मैट्रिक्स DOCX भी रखें", "reset_all": "🗑️ सारा डेटा हटाएँ",
        "st_libre": "LibreOffice उपलब्ध (DOCX/XLSX से PDF सर्वोत्तम)", "st_libre_missing": "LibreOffice नहीं है - सरल PDF विकल्प",
        "st_ocr": "OCR उपलब्ध", "st_ocr_missing": "OCR इंस्टॉल नहीं है",
        "saving": "फ़ाइलें सहेजी जा रही हैं", "processing": "प्रोसेस हो रहा है ...", "unzipping": "ZIP खोली जा रही है ...", "none": "दिखाने के लिए कुछ नहीं।",
        "no_files": "कोई समर्थित फ़ाइल नहीं मिली (PDF, DOCX, XLSX, ZIP)।",
        "upload_help": "PDF, DOCX, DOC, XLSX, XLS या ZIP। कुल {mb} MB तक।",
        "upload_size": "{mb} MB में से {used} उपयोग हुआ", "upload_too_big": "कुल आकार {mb} MB से अधिक है। कृपया दो भागों में अपलोड करें।",
        "unsupported": "असमर्थित फ़ाइलें छोड़ दी गईं: {files}", "unsupported_b": "{name}: असमर्थित फ़ाइलें छोड़ दी गईं - {files}",
        "col_file": "फ़ाइल", "col_size": "आकार", "col_corr": "शुद्धिपत्र?", "col_bidder": "बिडर", "col_nfiles": "फ़ाइलें",
        "col_how": "कैसे पहचाना", "col_include": "शामिल", "col_doc": "वांछित दस्तावेज़", "col_type": "प्रकार", "col_cat": "श्रेणी",
        "col_source": "स्रोत", "col_conf": "विश्वसनीयता", "col_ref": "निविदा संदर्भ", "col_kw": "कीवर्ड (मिलान हेतु)",
        "col_kw_help": "वे शब्द / वाक्यांश (English, हिन्दी, Hinglish) जो बिडर के दस्तावेज़ के फ़ाइल नाम या शीर्षक में आते हैं। ; से अलग करें",
        "col_mand_missing": "अनिवार्य अनुपलब्ध", "col_orig": "अपलोड की गई फ़ाइल", "col_inzip": "ZIP में फ़ाइल", "col_conv": "PDF बनाने का तरीका", "col_note": "टिप्पणी",
        "t1_head": "टेंडर / बिड दस्तावेज़", "t1_help": "टेंडर दस्तावेज़ और शुद्धिपत्र / संशोधन (PDF, DOCX, XLSX या ZIP) अपलोड करें। "
                                                      "जिन फ़ाइलों के नाम में 'corrigendum', 'addendum' या 'शुद्धिपत्र' हो वे अपने आप पहचानी जाती हैं।",
        "tender_title": "टेंडर का नाम / संख्या (DOCX में दिखेगा)", "tender_title_ph": "जैसे PWD/ELEC/2026/045 - एलईडी स्ट्रीट लाइट",
        "t1_upload": "टेंडर / बिड डेटा अपलोड करें", "btn_read": "टेंडर फ़ाइलें सहेजें और पढ़ें",
        "t1_done": "{n} टेंडर फ़ाइल(ें) तैयार", "t1_files": "टेंडर फ़ाइलें", "t1_corr_help": "संशोधन वाली फ़ाइलों पर 'शुद्धिपत्र?' का निशान लगाएँ ताकि वे बदलाव के रूप में पढ़ी जाएँ।",
        "t1_next": "अगला: टैब 2 में बिडर्स का डेटा अपलोड करें, फिर टैब 3 में विश्लेषण करें।",
        "t2_head": "बिडर्स के तकनीकी दस्तावेज़",
        "t2_help": "हर बिडर की एक ZIP (ZIP का नाम = बिडर का नाम) अपलोड करें जिसमें उसकी PDF / DOCX / XLSX फ़ाइलें हों। हर बिडर के लिए एक फ़ोल्डर वाली एक ही ZIP भी चलेगी।",
        "t2_mode": "बिडर्स कैसे व्यवस्थित हैं?", "t2_mode_help": "ऑटो मोड ZIP की बनावट से पहचानता है - नीचे नाम सुधार सकते हैं।",
        "mode_auto": "अपने आप पहचानें", "mode_zip_per_bidder": "हर ZIP = एक बिडर", "mode_folder_per_bidder": "ZIP के अंदर हर फ़ोल्डर = एक बिडर",
        "t2_upload": "बिडर्स का डेटा अपलोड करें", "btn_detect": "सहेजें और बिडर्स पहचानें", "t2_done": "{n} बिडर पहचाने गए",
        "t2_list": "बिडर्स", "t2_rename_help": "बिडर के नाम बदल सकते हैं - यही नाम मैट्रिक्स और ZIP में आएँगे।",
        "t2_view_files": "किसी बिडर की फ़ाइलें देखें", "t2_next": "अगला: टैब 3 में वांछित सूची बनाएँ और मिलान करें।",
        "t3_head": "विश्लेषण एवं वांछित दस्तावेज़ मैट्रिक्स", "t3_step_a": "चरण A - टेंडर पढ़कर वांछित दस्तावेज़ सूची बनाएँ",
        "need_tender": "पहले टैब 1 में टेंडर फ़ाइलें अपलोड करके पढ़ें।", "btn_analyze": "टेंडर का विश्लेषण करें",
        "analysis_mode_ai": "AI मोड चालू है", "analysis_mode_rules": "ऑफ़लाइन स्मार्ट-नियम मोड (मुफ़्त)", "analyzing": "टेंडर का विश्लेषण हो रहा है ...",
        "m_found": "मिले दस्तावेज़", "m_included": "शामिल", "m_mode": "मोड", "m_rules": "नियम", "none_found": "कोई दस्तावेज़ नहीं मिला। "
                                                                                                    "नीचे हाथ से पंक्तियाँ जोड़ें या AI मोड / OCR आज़माएँ।",
        "t3_edit_help": "सूची जाँचें और सुधारें: पंक्ति हटाने के लिए निशान हटाएँ, नाम या कीवर्ड बदलें, नीचे नई पंक्तियाँ जोड़ें। "
                        "शुद्धिपत्र से आई पंक्तियाँ 'स्रोत' में दिखती हैं।",
        "t3_step_b": "चरण B - बिडर्स के दस्तावेज़ों का मिलान", "need_bidders": "पहले टैब 2 में बिडर्स अपलोड करके पहचानें।",
        "need_list": "चरण A में कम से कम एक वांछित दस्तावेज़ बनाएँ (या जोड़ें)।", "btn_match": "बिडर्स के दस्तावेज़ मिलाएँ",
        "indexing": "बिडर्स की फ़ाइलें पढ़ी जा रही हैं ...", "matching": "मिलान हो रहा है ...", "t3_matrix": "वांछित दस्तावेज़ मैट्रिक्स (प्रीव्यू)",
        "table_view": "सादी तालिका दृश्य", "manual_title": "हाथ से सुधार", "manual_help": "बिडर और दस्तावेज़ चुनें, फिर बताएँ कि कौन-सी फ़ाइल(ें) उसे पूरा करती हैं। "
                                                      "कोई फ़ाइल न चुनने पर 'Not Submitted' हो जाएगा।",
        "manual_files": "इस दस्तावेज़ को पूरा करने वाली फ़ाइलें", "manual_apply": "लागू करें",
        "cands_title": "कठोरता स्तर से नीचे के संभावित मिलान", "cands_help": "ऐसी फ़ाइलें जो मिलती-जुलती लगीं पर स्वीकार नहीं हुईं। स्वीकार करने के लिए 'हाथ से सुधार' उपयोग करें।",
        "unmatched_title": "जो फ़ाइलें किसी वांछित दस्तावेज़ से नहीं मिलीं", "unmatched_n": "बिना मिलान की फ़ाइल(ें)", "unreadable_n": "बिना पढ़ने योग्य टेक्स्ट के",
        "t4_head": "डाउनलोड एवं प्रीव्यू", "need_match": "पहले टैब 3 में मिलान चलाएँ।",
        "t4_docx": "वांछित दस्तावेज़ सूची / मैट्रिक्स (DOCX)", "btn_build_docx": "DOCX बनाएँ / ताज़ा करें", "building": "बन रहा है ...",
        "dl_docx": "मैट्रिक्स डाउनलोड करें (DOCX)", "btn_prev_docx": "DOCX पृष्ठों का प्रीव्यू", "no_libre_preview": "पृष्ठ प्रीव्यू के लिए LibreOffice चाहिए; टैब 3 में मैट्रिक्स प्रीव्यू देखें।",
        "pages_shown": "{total} में से {n} पृष्ठ दिख रहे हैं",
        "t4_zip": "जमा किए गए दस्तावेज़ अलग-अलग PDF में (ZIP)",
        "t4_zip_help": "हर बिडर का अलग फ़ोल्डर; हर फ़ाइल का नाम  <क्र.सं.>_<दस्तावेज़>__<मूल नाम>.pdf  होता है ताकि मैट्रिक्स से मिलान आसान हो।",
        "btn_build_zip": "जमा दस्तावेज़ों की ZIP बनाएँ", "zip_ready": "ZIP तैयार: {n} PDF फ़ाइल(ें), {size}", "dl_zip": "ZIP डाउनलोड करें",
        "zip_contents": "ZIP की सामग्री", "zip_notes": "{n} फ़ाइल(ों) पर टिप्पणी है (सरल रूपांतरण या रूपांतरण विफल) - तालिका देखें।",
        "zip_preview": "ZIP के किसी दस्तावेज़ का प्रीव्यू", "zip_pick": "दस्तावेज़", "pages_to_show": "दिखाने के पृष्ठ", "btn_preview_pdf": "प्रीव्यू दिखाएँ",
        "notes_title": "टिप्पणियाँ एवं सीमाएँ",
        "notes_body": "- अपलोड सीमा: **प्रति टैब {mb} MB**। Streamlit Community Cloud में RAM सीमित (~2.7 GB) है, इसलिए बहुत बड़े डेटा को भागों में अपलोड करें।\n"
                      "- मिलान स्वचालित है (फ़ाइल नाम, पहले पृष्ठ का टेक्स्ट, कीवर्ड)। अंतिम मूल्यांकन से पहले **हमेशा जाँचें** - *हाथ से सुधार* उपयोग करें।\n"
                      "- स्कैन PDF / फ़ोटो के लिए **OCR** (साइडबार) चाहिए। पुराने फ़ॉन्ट (Kruti Dev) वाली हिन्दी PDF टेक्स्ट के रूप में नहीं पढ़ी जा सकतीं।\n"
                      "- अपलोड किया डेटा केवल इस सत्र के अस्थायी स्टोरेज में रहता है; काम पूरा होने पर *सारा डेटा हटाएँ* दबाएँ।",
    },
}


def tr(lang: str, key: str, **kw) -> str:
    s = STR.get(lang, STR["en"]).get(key) or STR["en"].get(key) or key
    try:
        return s.format(**kw) if kw else s
    except (KeyError, IndexError, ValueError):
        return s
