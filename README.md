# Gujarati Survey PDF Sequencer — UI Design Update

This package refreshes the app's visual design while retaining the same survey matching and PDF sequencing workflow from v4.

## What's changed
- Modern navy/teal gradient header and clean page background
- Numbered workflow sections and clearer headings
- Two-column upload and survey-sequence input layout
- More polished upload and sequence input styling
- Progress indicator, matched/missing metrics, diagnostics expander
- Prominent final PDF download button
- Responsive CSS adjustments for narrow screens

## Core workflow preserved
- Upload source PDF and paste requested survey list
- Match only the current `બ્લોક સરવે નંબર` field (not the old survey number field)
- Gujarati and English digit normalization
- Preserve the exact sequence and duplicates
- Exclude extra/unmatched pages from the final PDF
- CSV remains optional diagnostics only

## Deploy
Replace the existing repository files with these four files, commit, and redeploy/reboot the Streamlit app.

## Important
This is a design refresh of the v4 code. The underlying matching/OCR logic is unchanged. Syntax validation was performed; the visual appearance should be confirmed in the deployed Streamlit app.
