# Gujarati PDF Survey Sequencer — Field-focused OCR

This Streamlit app scans specifically the Gujarati field `બ્લોક/સરવે નંબર :` (including close variants) rather than searching arbitrary numbers on the page.

## Workflow
1. Upload the original PDF.
2. Paste survey numbers in the desired output sequence. Gujarati or Arabic digits are accepted; order and duplicate requests are preserved.
3. The app reads embedded PDF text, then if needed uses Gujarati+English Tesseract OCR at high resolution and multiple page segmentation modes. It also retries upper/middle/lower page regions.
4. It matches the detected value of the target field only, creates a new PDF in the exact requested sequence, and omits unmatched/extra pages.
5. Diagnostics show each page's detected survey field, method, and OCR preview.

## Streamlit Cloud
Replace `app.py`, `requirements.txt`, and `packages.txt` in your configured GitHub repository and commit. Ensure Streamlit Cloud is deploying the intended branch and main file. Reboot after deployment.

`packages.txt` installs Tesseract with Gujarati (`guj`) and English (`eng`) language data. OCR accuracy depends on scan quality and form layout; no sample PDF was provided for validation.
