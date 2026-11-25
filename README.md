# PDF Survey Sequencer

This Streamlit tool aims to create a separate PDF with only survey-number pages, ordered exactly as the pasted survey list.

1. Upload source PDF.
2. Paste survey numbers one per line.
3. Automatic field matching scans searchable text around Gujarati/English survey-number labels.
4. Review/change original source-page selections for unmatched or incorrect detections.
5. Download the final PDF. Only selected pages are included, in the exact master list order. Other pages are excluded.

Master list order and duplicate entries are preserved.

**OCR limitation:** Scanned/image-only PDFs are not OCRed by this version. If searchable text is absent, auto-match may find zero; use review page-number selections, or OCR the PDF first.

Deploy by replacing app.py, requirements.txt, packages.txt (empty) and README.md in the GitHub repo connected to Streamlit Cloud, commit, then redeploy.
