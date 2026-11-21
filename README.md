# 📑 Tender Matrix — टेंडर मैट्रिक्स

Streamlit web app (English + हिन्दी) jo tender/bid documents padhkar **"Wanting Document List / Matrix" (DOCX)** banata hai,
bidders ke documents se match karke har bidder ke column me **Submitted / Not Submitted** likhta hai, aur jo documents
Submitted hain unhe **alag-alag PDF files me ek ZIP** me deta hai.

## Features (aapki requirement ke hisab se)

| # | Requirement | App me |
|---|-------------|--------|
| 1 | Tender / corrigendum upload (docx, pdf, xlsx, zip) | Tab 1 — corrigendum files naam se auto-detect, manually bhi tick kar sakte hain |
| 2 | Bidders ka data (bidder-wise ZIP) | Tab 2 — "ZIP = bidder", "ZIP ke andar folder = bidder" ya Auto; nested ZIP, Hindi file names, wrapper folders sab handle |
| 3 | Wanting list DOCX + Submitted / Not Submitted | Tab 3 + Tab 4 — landscape DOCX, green/red cells, totals, "mandatory missing" row, Annexure A/B |
| 4 | Submitted documents → alag PDFs → ek ZIP | Tab 4 — `Bidder/NN_Document__original.pdf` (DOCX/XLSX/images PDF me convert) + `00_Match_Report.csv` |
| 6 | English + Hindi | UI dono bhasha me; tender/bidder documents ke liye 48 document-types ke English, Hindi aur Hinglish (`shapath patra`, `mukhtarnama`) aliases |
| 7 | Preview | Matrix preview, DOCX page preview, ZIP contents + PDF page preview |
| 8 | 500 MB per upload tab | `.streamlit/config.toml` → `maxUploadSize = 500` + 500 MB total check per tab |

## Folder structure

```
app.py                    Streamlit UI (4 tabs)
tendermatrix/             backend (no Streamlit import - testable)
  catalog.py              48 common tender documents, English/Hindi/Hinglish aliases  ← yahan naye document types add karein
  tender_analysis.py      offline rules: sections, lists, tables, annexures, corrigendum (added/deleted)
  llm.py                  optional AI mode (Claude)
  matching.py             file name + first page + body + fuzzy (typo) matching
  docx_report.py          matrix DOCX      package_zip.py  output ZIP      pdf_convert.py  DOCX/XLSX/image → PDF
tests/                    pytest suite + sample-data generator + Streamlit-less smoke test
.streamlit/config.toml    500 MB upload limit
packages.txt              apt packages for streamlit.app (LibreOffice, Hindi fonts, Tesseract Hindi OCR)
requirements.txt          Python packages
```

## GitHub + streamlit.app par deploy

1. GitHub par naya repository banayein (e.g. `tender-matrix-app`) aur **is folder ki saari files** upload / push karein
   (`.streamlit/config.toml`, `packages.txt`, `requirements.txt`, `app.py`, `tendermatrix/` zaroor hon).
2. <https://share.streamlit.io> → **Create app** → repository + branch select karein → **Main file path: `app.py`**.
3. *Advanced settings* me Python **3.12** (ya 3.11) chunein.
4. **Deploy**. Pehli baar 5–10 minute lag sakte hain (LibreOffice + Tesseract install hota hai).
5. (Optional, AI mode) App → **Settings → Secrets** me likhein:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```
   Bina key ke bhi app poora chalta hai (offline smart-rules).

> Streamlit Community Cloud ki RAM limit ~2.7 GB hai. 500 MB upload ke saath bahut bade ZIP ho to ek baar me kam bidders upload karein.

## Local run

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```
Best results ke liye machine par LibreOffice (DOCX/XLSX → PDF) aur Tesseract + Hindi data (OCR) install hona chahiye
(`sudo apt install libreoffice-writer libreoffice-calc tesseract-ocr tesseract-ocr-hin fonts-noto-core`).

## Kaam kaise karta hai

1. **Tender analysis** – "Documents required / Eligibility / पात्रता मानदंड / आवश्यक दस्तावेज़" jaise sections, numbered lists, tables aur
   "Annexure / Form / प्रपत्र" headings padhta hai; known documents (PAN, GST, EMD, ITR, Experience, ISO, MAF …) pehchanta hai;
   corrigendum me naya clause → *Corrigendum* source, "deleted / हटा दिया" → row band (verify karne ke liye).
   **AI mode** on ho to Claude lambe/complex tender ko padhta hai (relevant hisse chunk karke).
2. **Aap list ko edit karte hain** (row hatao, naam / keywords badlo, naya document jodo) – yeh sabse zaroori step hai.
3. **Matching** – har bidder file ka naam + folder, pehle page ka text, aur body text dekhta hai (typo bhi pakadta hai: `experiance`).
   Score ≥ strictness slider → **Submitted**. Kam score wale "possible matches" alag dikhte hain; *Manual correction* se kisi bhi cell ko theek karein.
4. **Output** – DOCX, ZIP (alag PDFs), `00_Match_Report.csv` (har match ka kaaran).

## Limitations (zaroor padhein)

- Matching automatic hai — **final evaluation se pehle verify karein**. Jab ek hi PDF me saare documents merge hain, to wo poori PDF match hoti hai
  (page-wise split nahi hota).
- Scanned PDF / photo ke liye sidebar me **OCR** on karein (dhima). Purane Kruti Dev jaise legacy-font wali Hindi PDF ka text sahi nahi padha jata.
- Offline rules tender ki bhasha ko samajhne me AI jitne strong nahi hain; complex tenders me AI mode ya manual edit use karein.
- Password-protected ZIP/PDF aur `.rar/.7z` support nahi hain (warning dikhti hai).
- Upload ka data sirf session ke temporary storage me rehta hai; kaam khatam hone par **Clear all data** dabayein.

## Tests

```bash
pip install pytest
python -m pytest -q tests                 # 27 tests: tender → matching → DOCX → ZIP, zip-slip/zip-bomb safety, OCR, AI (mock)
python tests/make_sample_data.py sample_data   # sample tender + 3 bidder ZIPs (English / Hindi / Hinglish) to try in the app
python tests/smoke_app.py                 # runs app.py end-to-end with a stub Streamlit
```
