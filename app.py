import io
import re
import unicodedata
import streamlit as st
import pandas as pd
import pymupdf

st.set_page_config(page_title="PDF Survey Sequencer", layout="wide")
st.title("PDF Survey Sequencer")
st.caption("Automatically find survey-number pages, export only matched pages, in your master-list order.")

GUJ_DIGITS = "૦૧૨૩૪૫૬૭૮૯"
ENG_DIGITS = "0123456789"
DIGIT_MAP = str.maketrans(GUJ_DIGITS, ENG_DIGITS)

def normalize_digits(value: str) -> str:
    return str(value).translate(DIGIT_MAP)

def normalize_text(value: str) -> str:
    value = normalize_digits(value)
    value = unicodedata.normalize("NFKC", value).lower()
    value = value.replace("પૈકી", "/")
    value = value.replace("paiki", "/").replace("p", "/")
    value = re.sub(r"\s+", "", value)
    value = re.sub(r"[^a-z0-9/.-]", "", value)
    value = value.replace(".", "/")
    value = re.sub(r"/+", "/", value)
    return value.strip("/")

def parse_master(raw: str):
    # Preserve order and duplicate rows. Accept one survey number per line,
    # or comma/semicolon-separated entries.
    lines = []
    for line in raw.splitlines():
        for part in re.split(r"[,;]", line):
            part = part.strip()
            if part:
                lines.append(normalize_digits(part))
    return lines

SURVEY_LABELS = [
    "બ્લોક/સરવે (સર્વે) નંબર",
    "બ્લોક સરવે નંબર",
    "સરવે નંબર",
    "સર્વે નંબર",
    "survey number",
    "survey no",
    "block survey",
    "block number",
]

def extract_survey_field(text: str) -> str:
    if not text:
        return ""
    text = normalize_digits(text)
    # First prioritize lines around the known Gujarati/English survey-field labels.
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for i, line in enumerate(lines):
        low = line.lower()
        if any(label.lower() in low for label in SURVEY_LABELS):
            # Survey number may be after colon on the same line or on next line.
            after = re.split(r"[:：]", line, maxsplit=1)
            if len(after) == 2 and after[1].strip():
                return after[1].strip()
            if i + 1 < len(lines):
                return lines[i + 1].strip()
    # Fallback: return full text for exact matching, not a guessed field.
    return ""

def contains_survey(text: str, survey: str) -> bool:
    norm_page = normalize_text(text)
    norm_survey = normalize_text(survey)
    if not norm_survey:
        return False
    # Exact normalized token match, with boundaries preventing 12 matching 112.
    pattern = r"(?<![a-z0-9])" + re.escape(norm_survey) + r"(?![a-z0-9])"
    return re.search(pattern, norm_page) is not None

def page_match(page_text: str, survey: str) -> bool:
    field = extract_survey_field(page_text)
    # Prefer the labeled field. If it was extracted, require match there.
    if field:
        if contains_survey(field, survey):
            return True
        # Some forms place the label and value in separate text blocks;
        # try matching the extracted field after normalization.
        return False
    # If no recognizable field label exists in text, use page text fallback.
    return contains_survey(page_text, survey)

def scan_pdf(doc, master):
    page_texts = [page.get_text("text") or "" for page in doc]
    results = []
    for row, survey in enumerate(master, start=1):
        candidates = [i + 1 for i, txt in enumerate(page_texts) if page_match(txt, survey)]
        results.append({"Master row": row, "Survey number": survey,
                       "Auto-detected source page(s)": ", ".join(map(str, candidates)) if candidates else "NOT FOUND",
                       "Select page": candidates[0] if candidates else None,
                       "Status": "Found" if candidates else "Not found"})
    return pd.DataFrame(results), page_texts

pdf_file = st.file_uploader("Step 1 — Upload original PDF", type=["pdf"])
master_raw = st.text_area(
    "Step 2 — Paste survey numbers in the exact required order (one per line)",
    height=220,
    placeholder="25\n27\n30\n31\n44\n52\n60"
)
master = parse_master(master_raw)

if pdf_file and master:
    try:
        original_bytes = pdf_file.getvalue()
        doc = pymupdf.open(stream=original_bytes, filetype="pdf")
        st.success(f"Original PDF: {len(doc)} pages | Master list: {len(master)} entries")
        with st.spinner("Scanning PDF text and matching survey numbers..."):
            auto_df, page_texts = scan_pdf(doc, master)

        found_count = int((auto_df["Status"] == "Found").sum())
        st.write(f"**Automatically found:** {found_count} / {len(master)} master-list entries")
        st.dataframe(auto_df[["Master row", "Survey number", "Auto-detected source page(s)", "Status"]],
                     hide_index=True, use_container_width=True)

        st.warning(
            "Automatic matching works best when PDF pages contain selectable text. "
            "If the PDF is scanned/image-only, pages may show NOT FOUND because Gujarati OCR is not included."
        )

        st.subheader("Step 3 — Review/adjust page selection (optional)")
        page_options = [None] + list(range(1, len(doc) + 1))
        review = auto_df[["Master row", "Survey number", "Select page"]].copy()
        review["Select page"] = pd.to_numeric(review["Select page"], errors="coerce")
        edited = st.data_editor(
            review,
            key="review_table",
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            column_config={
                "Master row": st.column_config.NumberColumn(disabled=True),
                "Survey number": st.column_config.TextColumn(disabled=True),
                "Select page": st.column_config.NumberColumn(
                    min_value=1, max_value=len(doc), step=1,
                    help="If a survey number was not found or the detected page is wrong, enter the correct source PDF page number."
                )
            }
        )

        selected = []
        missing = []
        for row_idx, survey in enumerate(master):
            raw_page = edited.iloc[row_idx]["Select page"]
            page_no = None if pd.isna(raw_page) else int(raw_page)
            if page_no is not None and 1 <= page_no <= len(doc):
                selected.append((row_idx + 1, survey, page_no))
            else:
                missing.append((row_idx + 1, survey))

        st.caption("Only selected pages are exported. Pages not selected are omitted. Output follows the master list order; duplicate list entries are preserved.")
        if missing:
            with st.expander(f"Skipped entries ({len(missing)})"):
                st.dataframe(pd.DataFrame(missing, columns=["Master row", "Survey number"]), hide_index=True)

        st.subheader("Step 4 — Download final PDF")
        if selected:
            output = pymupdf.open()
            for _, _, page_no in selected:
                output.insert_pdf(doc, from_page=page_no - 1, to_page=page_no - 1)
            pdf_out = output.tobytes(garbage=4, deflate=True)
            output.close()
            st.download_button(
                "⬇️ Download Final Sequenced PDF",
                data=pdf_out,
                file_name="survey_numbers_in_requested_sequence.pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True
            )
            st.success(f"Ready: {len(selected)} pages in the requested order. Extra/unselected pages removed.")
        else:
            st.info("No pages selected/found yet. Select source page numbers in the review table to generate the final PDF.")

        audit = pd.DataFrame({
            "Master row": range(1, len(master) + 1),
            "Survey number": master,
            "Auto detected page(s)": auto_df["Auto-detected source page(s)"],
            "Final selected page": edited["Select page"],
        })
        st.download_button("Download matching report (CSV)", audit.to_csv(index=False).encode("utf-8-sig"),
                          "survey_match_report.csv", "text/csv")
        doc.close()
    except Exception as err:
        st.error(f"PDF processing error: {err}")
elif pdf_file and not master:
    st.info("Paste your survey-number list to begin matching.")
else:
    st.info("Upload a PDF and paste the survey-number sequence to begin.")
