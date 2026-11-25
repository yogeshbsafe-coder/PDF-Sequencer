# PDF Survey Sequencer (v3)

Upload a searchable Gujarati land-record PDF and paste survey numbers in the exact output order.

- Matches page survey field candidates (Gujarati and English label variants, including imperfect text-extraction variants).
- Keeps master list order and duplicates.
- Exports only selected/matched pages; extra pages are omitted.
- Includes an editable source-page column for manual corrections.
- Matching diagnostic table shows extracted field candidates page-by-page.

**Scanned/image-only PDF limitation:** Gujarati OCR is not bundled. If PDF text extraction is empty or does not contain field text, automatic matching cannot detect it; use manual source-page mapping or OCR-convert the source PDF first.

Deploy by replacing app.py, requirements.txt, packages.txt (empty), and README.md in your connected GitHub repository, committing, and redeploying/rebooting Streamlit Cloud.
