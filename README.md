# PDF Survey Number Sequencer

A Streamlit app for making a new PDF from pages that match a supplied survey-number sequence.

## Features
- Upload a PDF and paste survey numbers in the required order.
- Gujarati digits are converted to English digits.
- Keeps matching pages in requested order and skips other pages.
- Shows requested numbers not found, repeated numbers detected in the PDF text, and numbers in the PDF but not in the list.
- Download the sequenced PDF and a report.

## Run locally
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## GitHub / Streamlit Cloud deployment
1. Create a GitHub repository and upload `app.py`, `requirements.txt`, and `README.md`.
2. In Streamlit Community Cloud, connect GitHub and select this repository.
3. Set the main file path to `app.py`, then deploy.

## Important
This version reads selectable text embedded in the PDF. Scanned/image-only PDFs must first be OCR-processed into searchable PDFs (Gujarati/English OCR language packs may be needed). OCR mistakes can affect matching. Review the matching preview before downloading.
