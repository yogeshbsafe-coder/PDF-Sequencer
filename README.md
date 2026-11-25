# PDF Survey Sequencer V2
Upload a PDF, paste the survey number order, review and edit the detected number/page map, and export only matched pages in the requested order.

Features: Gujarati/English digit conversion, OCR for scanned pages (Gujarati+English), page previews, editable per-page survey mapping, missing list numbers, extra mapped numbers, repeated numbers across pages, skipped page list, output PDF and report.

## Deploy
Upload/replace these files in your GitHub repository: `app.py`, `requirements.txt`, `packages.txt`, and `README.md`. Streamlit Cloud branch `main`, entry point `app.py`.

## Accuracy note
Automatic extraction can confuse survey numbers with dates, area values, or other numeric content. Always review/edit the mapping table before exporting. OCR depends on scan quality. Number forms are exact: `123`, `123/1`, and `123.001` are distinct unless you manually map them equivalently.
