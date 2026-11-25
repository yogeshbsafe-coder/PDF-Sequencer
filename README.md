# PDF Survey Sequencer

- Upload original PDF and paste the master survey list (one entry per line).
- Select source PDF page for each master-list row.
- Output includes mapped pages only, in the exact master-list order.
- Unmapped entries are skipped; duplicates in master list are preserved.
- The PDF download control is always rendered once the PDF and list are loaded; disabled until at least one row is mapped.

Deploy to Streamlit Community Cloud using `app.py`, `requirements.txt`, and an empty `packages.txt`.
