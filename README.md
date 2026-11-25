# Gujarati Survey PDF Sequencer (v4)

## Purpose
Upload the source land-record PDF and paste the survey-number master list. The app matches **only the current `બ્લોક સરવે નંબર` field**, explicitly ignoring the `જૂનો બ્લોક/સરવે નંબર` field and all other numbers. It creates a separate PDF in the exact master-list order and excludes all unmatched/extra pages.

## Files
- `app.py`: Streamlit application
- `requirements.txt`: Python libraries
- `packages.txt`: Tesseract and Gujarati language system packages for Streamlit Cloud

## Deploy
1. Replace the files in your GitHub repository with these four files.
2. Commit and push.
3. In Streamlit Cloud, verify the app repository, branch, and main file path (`app.py`), then reboot/redeploy.

## Use
1. Upload original PDF.
2. Paste survey numbers (one per line; Gujarati or English numerals accepted).
3. Enable OCR for scanned PDFs.
4. Download **DOWNLOAD SEQUENCED PDF** after pages match.

## Detection
- Searchable PDF: extracts embedded text and reads only the target current-field label/value.
- Scanned PDF: OCR is attempted on the upper 52% page crop at 3x resolution using Gujarati + English Tesseract, then extraction is restricted to a line containing the target label. It does not use the old survey field.
- If Tesseract Gujarati language data is unavailable in deployment, diagnostics indicate the missing language pack.

## Important limitation
The OCR target-field crop is based on the supplied form layout and is set to the upper 52% of the page. If your PDF uses a different page layout, upload a sample PDF so the crop can be calibrated. This version has syntax validation only; it has not been tested against your original full PDF.
