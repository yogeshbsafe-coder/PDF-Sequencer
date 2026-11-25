# PDF Survey Sequencer

## What this app does
1. Upload a Gujarati land-record PDF.
2. Paste your survey-number master list in the exact desired order.
3. The app scans page text and tries to identify survey-number pages, prioritizing the labeled survey field.
4. Review or correct page selections if needed.
5. Download a new PDF containing only selected pages, in the master-list order. Extra/unselected pages are omitted.

## Important limitation
Automatic matching requires searchable/selectable PDF text. Scanned image-only pages need Gujarati OCR, which is not bundled in this lightweight Streamlit deployment. Such entries appear as NOT FOUND and can be assigned a page number manually in the review table.

## Deploy
Upload/replace these files in the GitHub repository used by Streamlit Cloud:
- `app.py`
- `requirements.txt`
- `packages.txt` (empty)

Then commit and push. In Streamlit Cloud, confirm the app is connected to the correct repository, branch, and `app.py`, then reboot/redeploy.
