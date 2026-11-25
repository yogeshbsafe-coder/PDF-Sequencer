# PDF Survey Sequencer & Survey Number Editor

Streamlit app to map PDF pages to a master survey-number sequence, review/edit page mappings, optionally replace a selectable printed survey number on a page, and export the final PDF in master-list order.

## Features
- Paste a survey-number list in Gujarati or English digits; line breaks, commas and semicolons are supported.
- Analyze page text and optionally OCR pages with little/no selectable text.
- Editable page-to-survey-number mapping.
- Show missing list entries, extra mapped numbers, and skipped pages.
- Preview source pages and extracted text.
- Optional per-page printed-number replacement: enter the old searchable number and the replacement. The app attempts replacement only when the old value is selectable text in the PDF; scanned image text cannot be edited by this method and is reported.
- Export reordered PDF and CSV correction report.

## Run locally
1. Install Python 3.10+.
2. Install packages: `pip install -r requirements.txt`
3. Install Tesseract OCR and Gujarati language data if OCR is desired. On Debian/Ubuntu: `sudo apt-get install tesseract-ocr tesseract-ocr-gu`.
4. Run: `streamlit run app.py`

## Streamlit Cloud deployment
Upload `app.py`, `requirements.txt`, `packages.txt`, and `README.md` to your GitHub repository. Select the `main` branch and `app.py` as the app entry point.


## Important accuracy / editing notes
- Detection is a suggestion. Verify every page mapping before exporting.
- `123`, `123/1`, and `123.001` are treated as distinct values.
- Replacement uses searchable PDF text, not OCR coordinates. For scanned PDFs or unusual text layout, the correction may not be applied. Always check the output PDF visually.
- When the same source page maps to more than one requested number, that page is included only once in the final PDF.
