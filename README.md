# PDF Survey Sequencer — Exact Master List Sequence

## What this version does
- Preserves the pasted master survey list order exactly (no numerical sorting).
- Preserves duplicate entries in the master list.
- Suggests PDF pages only from exact survey-number text candidates; suggestions are not assumed correct.
- Allows the user to manually assign the correct PDF page to each list row.
- Requires every master-list row to be mapped before export.
- Exports one page per master-list row in exact top-to-bottom order; source pages can intentionally repeat.
- Includes a CSV mapping audit download.

## Deploy
1. Replace repository files with `app.py`, `requirements.txt`, `packages.txt`, and `README.md`.
2. Commit and push to GitHub.
3. Streamlit Cloud will redeploy.

Note: Gujarati PDFs with embedded/garbled text can produce unreliable page suggestions. Verify each row with the page preview before exporting. This app does not alter the printed survey-number text on PDF pages; it only sequences pages.
