# PDF Survey Sequencer — Updated Matching Workflow

This build follows the intended sequence-export workflow:
- Upload the source PDF.
- Paste survey numbers in the exact sequence desired (one per line or comma/semicolon-separated).
- The app reads each page's survey-number field and creates an index.
- It matches the master list to page survey keys.
- It exports a PDF containing only matched/selected pages, in the master-list order.
- Extra pages and non-matching survey pages are excluded.
- Duplicate survey numbers in the master list remain duplicated in the final output.
- Optional CSV is only a matching audit; PDF is the main output.

## Matching notes
- Gujarati digits are converted to Arabic digits for matching.
- Common `પૈકી` / `paiki` notation is normalized to a `p` marker.
- The app prioritizes the survey-number field labels and value following the label.
- If the PDF text extraction does not expose the survey field, the item may be `NOT FOUND`. This build does not use OCR and does not guess from random page numbers.
- When a survey number occurs on multiple source pages, the first is selected by default; the review table allows selecting the correct page.
- Unmatched entries are skipped and shown in the skipped list.

## Deploy on Streamlit Cloud
Replace the files in your GitHub repository with the files in this ZIP. Ensure the Streamlit app settings point to the correct repo, branch, and `app.py`, then commit/push and reboot the app.

Files: `app.py`, `requirements.txt`, `packages.txt` (empty), `README.md`.
