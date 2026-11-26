# Gujarati Survey PDF Sequencer — Faster Processing Update

This update preserves the existing current-field detection, Gujarati/English numeral normalization, paiki/nested sub-survey matching, exact sequence ordering, and PDF export behavior while reducing OCR time.

## Performance improvements
- Render only the upper 48% of the PDF page directly (no full-page rasterization), at 2x instead of 3x.
- OCR first with one mode (`--psm 6`); retry using `--psm 11` only when the target field is not detected.
- Cache survey detection results for the uploaded PDF and OCR setting, so Streamlit reruns caused by UI interactions do not repeat OCR.
- Embedded PDF text is checked first; OCR runs only for pages where the current survey-number field is not found in embedded text.

## Deploy
Replace `app.py`, `requirements.txt`, `packages.txt`, and `README.md` in your GitHub repository, commit, and redeploy/reboot Streamlit Cloud.

## Requirements
- Searchable/text PDFs can be detected through embedded text extraction without OCR.
- Scanned PDFs require Tesseract with Gujarati (`guj`) and English (`eng`) language data installed.
- Only the current `બ્લોક સરવે નંબર` field is used; the old survey-number field is excluded.
- Main survey numbers and nested `પૈકી` sub-survey paths are matched in the user's exact requested order.
