# PDF Survey Sequencer (Automatic PDF generation)

Streamlit app that extracts survey identifiers from PDF text around Gujarati/English survey-number labels, matches them to the user's ordered list, and outputs a new PDF containing only matching pages in that order. Extra pages are excluded. Duplicate list entries are preserved when separate matching source pages exist.

## Deploy
1. Replace `app.py`, `requirements.txt`, `packages.txt` in your GitHub repo.
2. Commit changes and ensure Streamlit Cloud points to the correct repo, branch, and `app.py`.
3. Reboot/redeploy.

## Limitations
Text-based PDFs are supported. Image-only/scanned PDFs require OCR, which is not included in this package. Diagnostics show what survey identifiers were detected per page. Matching uses exact normalized survey identifiers.
