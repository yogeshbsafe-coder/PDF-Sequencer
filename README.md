# PDF Survey Sequencer (OCR fallback)

1. Upload the original PDF.
2. Paste the requested survey sequence, one per line.
3. The app reads embedded PDF text first. If no survey value is detected on a page, it runs Gujarati + English Tesseract OCR (if installed).
4. Pages matching the requested survey list are assembled in the exact sequence. Unrequested pages are omitted.
5. Download the sequenced PDF. CSV is optional.

## Deploy to Streamlit Community Cloud
Replace `app.py`, `requirements.txt`, and `packages.txt` in the configured GitHub repository/branch. Commit, then redeploy/reboot the Streamlit app. Ensure `packages.txt` is at repository root and contains the Tesseract packages listed here.

Note: OCR accuracy varies with scan quality, print layout, and Gujarati recognition. Check the detection-details table if any requested survey number is missing. The code has been syntax-checked; OCR matching should be validated on your actual PDF before relying on it.
