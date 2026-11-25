import re
from collections import defaultdict

import pandas as pd
import streamlit as st

try:
    import pymupdf as fitz
except ImportError:
    import fitz

try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except Exception:
    pytesseract = None
    Image = None
    OCR_AVAILABLE = False

st.set_page_config(page_title="PDF Survey Sequencer & Editor", page_icon="📄", layout="wide")
st.title("📄 PDF Survey Sequencer & Survey Number Editor")
st.write(
    "Arrange PDF pages according to your master survey list, review detected numbers, "
    "and optionally correct a printed survey number on a page."
)

GUJ_DIGITS = str.maketrans("૦૧૨૩૪૫૬૭૮૯", "0123456789")
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
EN_DIGITS_TO_GUJ = str.maketrans("0123456789", "૦૧૨૩૪૫૬૭૮૯")


def normalize(value):
    value = str(value or "").translate(GUJ_DIGITS).translate(ARABIC_DIGITS).strip()
    return re.sub(r"\s+", "", value)


def gujarati_digits(value):
    return str(value).translate(EN_DIGITS_TO_GUJ)


def parse_list(raw):
    items = re.split(r"[,;\n]+", raw or "")
    result = []
    for item in items:
        number = normalize(item)
        if number and number not in result:
            result.append(number)
    return result


def extract_text(page):
    try:
        return page.get_text("text") or ""
    except Exception:
        return ""


def available_ocr_languages():
    if not OCR_AVAILABLE:
        return []
    try:
        return pytesseract.get_languages(config="")
    except Exception:
        return []


OCR_LANGUAGES = available_ocr_languages()
GUJ_OCR_AVAILABLE = "guj" in OCR_LANGUAGES or "gu" in OCR_LANGUAGES


def run_ocr(page):
    if not OCR_AVAILABLE:
        return ""
    try:
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        lang = "eng+guj" if GUJ_OCR_AVAILABLE else "eng"
        try:
            return pytesseract.image_to_string(image, lang=lang)
        except Exception:
            # OCR is optional; try English only as a fallback.
            try:
                return pytesseract.image_to_string(image, lang="eng")
            except Exception:
                return ""
    except Exception:
        return ""


def number_candidates(text):
    text = text.translate(GUJ_DIGITS).translate(ARABIC_DIGITS)
    matches = re.findall(r"(?<![\w])\d+(?:[./-]\d+)*(?![\w])", text)
    return list(dict.fromkeys(normalize(item) for item in matches if normalize(item)))


def page_preview(page):
    return page.get_pixmap(matrix=fitz.Matrix(1.25, 1.25), alpha=False).tobytes("png")


def text_safe(value):
    return "" if pd.isna(value) else str(value)


def replace_text_value(page, old_value, new_value):
    """Replace matching selectable text; scanned image text cannot be changed by this method."""
    old_value = normalize(old_value)
    new_value = str(new_value).strip()
    if not old_value or not new_value or old_value == normalize(new_value):
        return 0, "No replacement needed"

    search_forms = list(dict.fromkeys([old_value, gujarati_digits(old_value)]))
    rectangles = []
    for form in search_forms:
        try:
            rectangles.extend(page.search_for(form))
        except Exception:
            pass

    unique_rectangles = []
    for rect in rectangles:
        duplicate = any(
            abs(rect.x0 - other.x0) < 1
            and abs(rect.y0 - other.y0) < 1
            and abs(rect.x1 - other.x1) < 1
            and abs(rect.y1 - other.y1) < 1
            for other in unique_rectangles
        )
        if not duplicate:
            unique_rectangles.append(rect)

    if not unique_rectangles:
        return 0, "Old number not found as selectable PDF text; scanned/image text needs manual editing"

    # White-redact only the found old-number text rectangles, then write the new value.
    for rect in unique_rectangles:
        page.add_redact_annot(rect, fill=(1, 1, 1))
    page.apply_redactions()

    replacement = new_value
    for rect in unique_rectangles:
        box = fitz.Rect(rect.x0, rect.y0 - 0.5, rect.x1 + max(2, rect.width * 0.2), rect.y1 + 0.5)
        base_size = max(6, min(12, rect.height * 0.82))
        inserted = False
        for font_size in range(int(base_size), 4, -1):
            try:
                result = page.insert_textbox(
                    box, replacement, fontsize=font_size, fontname="helv", color=(0, 0, 0), align=0
                )
                if result >= 0:
                    inserted = True
                    break
            except Exception:
                continue
        if not inserted:
            try:
                page.insert_text((rect.x0, rect.y1), replacement, fontsize=7, fontname="helv", color=(0, 0, 0))
            except Exception:
                pass
    return len(unique_rectangles), "Replacement attempted on selectable text"


uploaded_pdf = st.file_uploader("Upload original PDF", type=["pdf"])

if uploaded_pdf is not None:
    pdf_bytes = uploaded_pdf.getvalue()
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as error:
        st.error(f"Could not open PDF: {error}")
        st.stop()

    st.success(f"PDF loaded: {len(doc)} pages")
    master_list_text = st.text_area(
        "Paste master survey-number list in the exact required order",
        placeholder="Example:\n12\n12/1\n13\n14\n25/2",
        height=160,
    )
    desired_numbers = parse_list(master_list_text)

    use_ocr = st.checkbox("Try OCR on pages with little/no selectable text (if installed)", value=True)
    if use_ocr and not OCR_AVAILABLE:
        st.warning("OCR libraries are unavailable. PDF text extraction will still work; scanned pages may need manual mapping.")
    elif use_ocr and OCR_AVAILABLE and not GUJ_OCR_AVAILABLE:
        st.warning("Gujarati OCR language data is not installed. OCR will use English only; Gujarati numbers may need manual review.")

    if st.button("Analyze PDF pages", type="primary", disabled=not bool(desired_numbers)):
        page_rows = []
        progress = st.progress(0)
        for index, page in enumerate(doc):
            page_text = extract_text(page)
            ocr_used = False
            if use_ocr and len(page_text.strip()) < 25 and OCR_AVAILABLE:
                ocr_text = run_ocr(page)
                if ocr_text.strip():
                    page_text += "\n" + ocr_text
                    ocr_used = True
            detected = number_candidates(page_text)
            suggested = [number for number in detected if number in desired_numbers]
            page_rows.append(
                {
                    "PDF Page": index + 1,
                    "Survey number assigned (edit)": ", ".join(suggested),
                    "Printed number to replace (optional)": "",
                    "Replace with (optional)": "",
                    "Detected candidates": ", ".join(detected),
                    "OCR used": "Yes" if ocr_used else "No",
                    "Page text sample": page_text[:1800],
                }
            )
            progress.progress((index + 1) / max(len(doc), 1))
        st.session_state.survey_rows = page_rows
        st.session_state.survey_desired = desired_numbers
        st.session_state.survey_pdf_bytes = pdf_bytes
        st.session_state.survey_filename = uploaded_pdf.name
        st.success("Analysis complete. Review/edit the mapping table before exporting.")

if "survey_rows" in st.session_state:
    rows = st.session_state.survey_rows
    desired_numbers = st.session_state.survey_desired
    pdf_bytes = st.session_state.survey_pdf_bytes
    source_doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    st.header("Step 2 — Review page mapping and optional correction fields")
    st.info(
        "Edit the assigned survey-number column to map each page correctly. To attempt a printed-number correction, "
        "enter the old printed number and the new number in the two optional columns. Automatic correction works "
        "only for selectable PDF text, not text that exists only in a scanned image."
    )

    page_mapping_df = pd.DataFrame(rows)
    editable = st.data_editor(
        page_mapping_df[
            [
                "PDF Page",
                "Survey number assigned (edit)",
                "Printed number to replace (optional)",
                "Replace with (optional)",
                "Detected candidates",
                "OCR used",
            ]
        ],
        hide_index=True,
        width="stretch",
        num_rows="fixed",
        disabled=["PDF Page", "Detected candidates", "OCR used"],
        column_config={
            "Survey number assigned (edit)": st.column_config.TextColumn(
                help="Assign the exact number from the master list. Multiple numbers can be comma-separated."
            ),
            "Printed number to replace (optional)": st.column_config.TextColumn(
                help="Enter the old printed survey number; leave blank if no change is required."
            ),
            "Replace with (optional)": st.column_config.TextColumn(
                help="Enter the corrected survey number to print in place of the old value."
            ),
        },
    )

    with st.expander("Preview original page and extracted text"):
        selected_page = st.selectbox("Source PDF page", list(range(1, len(source_doc) + 1)))
        st.image(page_preview(source_doc[selected_page - 1]), caption=f"Original PDF page {selected_page}")
        st.text_area("Extracted text preview", rows[selected_page - 1]["Page text sample"], height=140, disabled=True)

    mapping = defaultdict(list)
    replacements_by_page = {}
    for _, row in editable.iterrows():
        page_num = int(row["PDF Page"])
        assigned_values = re.split(r"[,;\n]+", text_safe(row["Survey number assigned (edit)"]))
        for value in assigned_values:
            key = normalize(value)
            if key:
                mapping[key].append(page_num)
        old_number = normalize(row["Printed number to replace (optional)"])
        new_number = text_safe(row["Replace with (optional)"]).strip()
        if old_number and new_number:
            replacements_by_page[page_num] = (old_number, new_number)

    ordered_pages = []
    matched = []
    missing = []
    for number in desired_numbers:
        pages = mapping.get(number, [])
        if pages:
            matched.append((number, pages))
            for page_number in pages:
                if page_number not in ordered_pages:
                    ordered_pages.append(page_number)
        else:
            missing.append(number)

    extra_numbers = sorted(set(mapping) - set(desired_numbers))
    skipped_pages = sorted(set(range(1, len(source_doc) + 1)) - set(ordered_pages))

    st.header("Step 3 — Matching results")
    metric_cols = st.columns(4)
    metric_cols[0].metric("Source pages", len(source_doc))
    metric_cols[1].metric("Output pages", len(ordered_pages))
    metric_cols[2].metric("Missing master-list numbers", len(missing))
    metric_cols[3].metric("Skipped pages", len(skipped_pages))

    if matched:
        st.subheader("Survey number → original page(s)")
        st.dataframe(
            pd.DataFrame(
                [{"Survey number": number, "Original page(s)": ", ".join(map(str, pages))} for number, pages in matched]
            ),
            hide_index=True,
            width="stretch",
        )

    left_col, right_col = st.columns(2)
    with left_col:
        st.subheader("Missing survey numbers")
        if missing:
            st.dataframe(pd.DataFrame({"Missing number": missing}), hide_index=True, width="stretch")
        else:
            st.success("All master-list numbers are mapped.")
    with right_col:
        st.subheader("Mapped but not requested")
        if extra_numbers:
            st.dataframe(pd.DataFrame({"Extra number": extra_numbers}), hide_index=True, width="stretch")
        else:
            st.success("No extra mapped numbers.")

    if skipped_pages:
        st.caption("Skipped source pages: " + ", ".join(map(str, skipped_pages)))

    if ordered_pages and st.button("Build final PDF (sequence + optional number corrections)", type="primary"):
        source = fitz.open(stream=pdf_bytes, filetype="pdf")
        output = fitz.open()
        correction_report = []
        for page_number in ordered_pages:
            if page_number in replacements_by_page:
                old_number, new_number = replacements_by_page[page_number]
                count, status = replace_text_value(source[page_number - 1], old_number, new_number)
                correction_report.append(
                    {
                        "Source page": page_number,
                        "Old number": old_number,
                        "New number": new_number,
                        "Occurrences changed/attempted": count,
                        "Status": status,
                    }
                )
            output.insert_pdf(source, from_page=page_number - 1, to_page=page_number - 1)

        final_pdf_bytes = output.tobytes(garbage=4, deflate=True)
        st.session_state.final_survey_pdf = final_pdf_bytes
        st.session_state.survey_correction_report = correction_report
        output.close()
        source.close()
        st.success("Final PDF generated. Check the correction report before downloading.")

    if "final_survey_pdf" in st.session_state:
        st.download_button(
            "Download final sequenced PDF",
            data=st.session_state.final_survey_pdf,
            file_name="survey_numbers_corrected_sequenced.pdf",
            mime="application/pdf",
        )
        correction_report = st.session_state.get("survey_correction_report", [])
        if correction_report:
            st.subheader("Survey-number correction report")
            report_df = pd.DataFrame(correction_report)
            st.dataframe(report_df, hide_index=True, width="stretch")
            st.download_button(
                "Download correction report CSV",
                report_df.to_csv(index=False).encode("utf-8-sig"),
                file_name="survey_correction_report.csv",
                mime="text/csv",
            )
        else:
            st.caption("No number corrections were entered. The PDF was reordered only.")

    source_doc.close()
else:
    st.info("Upload your PDF, paste the master survey-number list, and click Analyze PDF pages.")
