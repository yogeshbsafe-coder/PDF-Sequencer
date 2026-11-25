# PDF Survey Sequencer & Editor

Streamlit application to upload a PDF, enter a master survey-number list in the desired order, review/edit page mappings, and export a reordered PDF. Optional correction fields attempt to replace old survey-number text with a new value on pages where the old value is selectable PDF text.

## Files
- `app.py` — application
- `requirements.txt` — Python dependencies
- `packages.txt` — system package list for Streamlit Cloud

## Deploy on Streamlit Cloud
1. Replace the files in your GitHub repository with these files.
2. Set the main file path to `app.py`.
3. Commit and push to the deployment branch.
4. Streamlit Cloud will redeploy.

## OCR behavior
Only the basic `tesseract-ocr` package is required. Gujarati OCR language data is optional and may not be available in every deployment image. The app checks the installed Tesseract languages at runtime and uses Gujarati+English if Gujarati language data is present; otherwise it falls back to English OCR. OCR can be disabled in the app.

## Accuracy note
Detection is a suggestion and may mistake dates, areas, or other numbers for survey numbers. Review and correct the page mapping before exporting. Automatic number replacement is limited to selectable text; scanned/image text requires manual editing in a PDF editor. Always inspect the final PDF before using it officially.
