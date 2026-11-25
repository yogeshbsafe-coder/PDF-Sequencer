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
    OCR_AVAILABLE = False

st.set_page_config(page_title="PDF Survey Sequencer", page_icon="📄", layout="wide")
st.title("📄 PDF Survey Sequencer")
st.write("Upload a PDF, enter the survey-number sequence, review page detections, and export pages in the requested order.")

GUJ_DIGITS = str.maketrans("૦૧૨૩૪૫૬૭૮૯", "0123456789")
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

def normalize(value):
    """Normalize Gujarati/Arabic numerals and remove surrounding whitespace."""
    value = str(value or "").translate(GUJ_DIGITS).translate(ARABIC_DIGITS)
    value = value.strip()
    value = re.sub(r"\s+", "", value)
    return value

def parse_requested_numbers(raw):
    # Preserve entered order. Split on commas, semicolons, whitespace, or new lines.
    items = re.split(r"[,;\n]+", raw or "")
    output = []
    for item in items:
        key = normalize(item)
        if key and key not in output:
            output.append(key)
    return output

def extract_text(page):
    try:
        return page.get_text("text") or ""
    except Exception:
        return ""

def run_ocr(page):
    if not OCR_AVAILABLE:
        return ""
    try:
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        # Gujarati OCR language may not be installed; use English as fallback.
        try:
            return pytesseract.image_to_string(image, lang="eng+guj")
        except Exception:
            return pytesseract.image_to_string(image, lang="eng")
    except Exception:
        return ""

def candidates_from_text(text):
    # Broad numeric candidates only. Users must review and edit these suggestions.
    text = text.translate(GUJ_DIGITS).translate(ARABIC_DIGITS)
    # Handles integers, decimals, and slash-separated sub-number patterns.
    found = re.findall(r"(?<![\w])\d+(?:[./-]\d+)*(?![\w])", text)
    cleaned = []
    for item in found:
        item = normalize(item)
        if item and item not in cleaned:
            cleaned.append(item)
    return cleaned

def page_preview(page):
    pix = page.get_pixmap(matrix=fitz.Matrix(1.3, 1.3), alpha=False)
    return pix.tobytes("png")

def safe_text(value):
    if pd.isna(value):
        return ""
    return str(value)

uploaded = st.file_uploader("Upload source PDF", type=["pdf"])
if uploaded:
    try:
        pdf_bytes = uploaded.getvalue()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        st.error(f"Could not open this PDF: {exc}")
        st.stop()

    st.success(f"PDF loaded successfully: {len(doc)} pages")
    raw_list = st.text_area(
        "Enter required survey numbers in the exact sequence",
        placeholder="Example: 12, 12/1, 13, 14, 25/2",
        height=130,
        help="Enter one survey number per line or separate them with commas. Gujarati digits are supported."
    )
    wanted = parse_requested_numbers(raw_list)

    use_ocr = st.checkbox("Use OCR on pages with little/no selectable text (if OCR is installed)", value=True)
    if use_ocr and not OCR_AVAILABLE:
        st.info("OCR Python library is not installed. Text-based PDF extraction will still work. OCR is optional.")

    if st.button("Analyze PDF pages", type="primary", disabled=not bool(wanted)):
        infos = []
        progress = st.progress(0)
        for idx, page in enumerate(doc):
            text = extract_text(page)
            ocr_used = False
            if use_ocr and len(text.strip()) < 25 and OCR_AVAILABLE:
                ocr_text = run_ocr(page)
                if ocr_text.strip():
                    text = text + "\n" + ocr_text
                    ocr_used = True
            detected = candidates_from_text(text)
            # Suggested mapping: keep candidates that exactly match requested numbers,
            # otherwise leave empty so the user can manually review rather than over-match.
            suggested = [num for num in detected if num in wanted]
            infos.append({
                "PDF page": idx + 1,
                "Survey number(s) — edit if needed": ", ".join(suggested),
                "Label detections": "",
                "All detected number candidates": ", ".join(detected),
                "OCR used": "Yes" if ocr_used else "No",
                "Text preview": text[:2500],
            })
            progress.progress((idx + 1) / max(len(doc), 1))
        st.session_state["survey_infos"] = infos
        st.session_state["survey_wanted"] = wanted
        st.session_state["survey_pdf_bytes"] = pdf_bytes
        st.session_state["survey_filename"] = uploaded.name
        st.success("Analysis complete. Review and correct the page mapping below.")

if "survey_infos" in st.session_state and "survey_wanted" in st.session_state:
    infos = st.session_state["survey_infos"]
    wanted = st.session_state["survey_wanted"]
    pdf_bytes = st.session_state["survey_pdf_bytes"]
    st.header("Step 2 — Review and correct the page mapping")
    st.warning("Auto-detection is a suggestion. It can confuse survey numbers with dates, areas, amounts, or other numbers. Correct the editable Survey number(s) column. If a page contains multiple survey numbers, separate them with commas.")
    df = pd.DataFrame(infos)
    editable = st.data_editor(
        df[[
            "PDF page",
            "Survey number(s) — edit if needed",
            "Label detections",
            "All detected number candidates",
            "OCR used"
        ]],
        hide_index=True,
        width="stretch",
        num_rows="fixed",
        disabled=[
            "PDF page",
            "Label detections",
            "All detected number candidates",
            "OCR used"
        ],
        column_config={
            "PDF page": st.column_config.NumberColumn(),
            "Label detections": st.column_config.TextColumn(),
            "All detected number candidates": st.column_config.TextColumn(),
            "OCR used": st.column_config.TextColumn(),
            "Survey number(s) — edit if needed": st.column_config.TextColumn(
                help="Edit manually; multiple numbers on a page separated by commas."
            ),
        },
    )

    with st.expander("View original PDF page to verify mapping"):
        page_num = st.selectbox("Select source page", list(range(1, len(doc) + 1)))
        st.image(page_preview(doc[page_num - 1]), caption=f"Original source page {page_num}", width="stretch")
        st.text_area("Extracted text", infos[page_num - 1]["Text preview"], height=150, disabled=True)

    mapping = defaultdict(list)
    for _, row in editable.iterrows():
        p = int(row["PDF page"])
        val = safe_text(row["Survey number(s) — edit if needed"])
        for item in re.split(r"[,;\n]+", val):
            key = normalize(item)
            if key:
                mapping[key].append(p)

    matched = []
    missing = []
    output_pages = []
    for number in wanted:
        pages = mapping.get(number, [])
        if pages:
            matched.append((number, pages))
            for p in pages:
                if p not in output_pages:
                    output_pages.append(p)
        else:
            missing.append(number)

    repeated = {n: sorted(set(ps)) for n, ps in mapping.items() if len(set(ps)) > 1}
    not_requested = sorted(set(mapping) - set(wanted))
    skipped = sorted(set(range(1, len(doc) + 1)) - set(output_pages))

    st.header("Step 3 — Matching results")
    a, b, c, d = st.columns(4)
    a.metric("Source pages", len(doc))
    b.metric("Pages in output", len(output_pages))
    c.metric("Missing list numbers", len(missing))
    d.metric("Skipped pages", len(skipped))

    st.subheader("Matched numbers → original PDF pages")
    if matched:
        st.dataframe(
            pd.DataFrame([{"Survey number": n, "Original page(s)": ", ".join(map(str, ps))} for n, ps in matched]),
            hide_index=True,
            width="stretch"
        )
    else:
        st.warning("No matches yet. Edit the page map above, then recheck.")

    left, right = st.columns(2)
    with left:
        st.subheader("Missing survey numbers")
        if missing:
            st.dataframe(pd.DataFrame({"Missing survey number": missing}), hide_index=True, width="stretch")
            st.download_button("Download missing numbers CSV", pd.DataFrame({"Missing survey number": missing}).to_csv(index=False).encode("utf-8-sig"), "missing_survey_numbers.csv", "text/csv")
        else:
            st.success("No missing survey numbers in the entered list.")
    with right:
        st.subheader("Mapped but not requested")
        if not_requested:
            st.dataframe(pd.DataFrame({"Extra mapped number": not_requested}), hide_index=True, width="stretch")
        else:
            st.info("No extra mapped numbers.")

    st.subheader("Numbers mapped to multiple PDF pages")
    if repeated:
        st.dataframe(pd.DataFrame([{"Survey number": n, "Pages": ", ".join(map(str, ps))} for n, ps in repeated.items()]), hide_index=True, width="stretch")
    else:
        st.success("No duplicate page mapping detected.")

    st.subheader("Skipped source pages")
    if skipped:
        st.write(", ".join(map(str, skipped)))
    else:
        st.success("All source pages are included in the output.")

    if output_pages:
        output_doc = fitz.open()
        source_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for p in output_pages:
            output_doc.insert_pdf(source_doc, from_page=p - 1, to_page=p - 1)
        out_bytes = output_doc.tobytes()
        output_doc.close()
        source_doc.close()
        st.download_button(
            "Download reordered PDF",
            data=out_bytes,
            file_name="survey_numbers_sequenced.pdf",
            mime="application/pdf",
            type="primary"
        )
        st.caption("Output pages follow the requested survey-number order. When one survey number is mapped to multiple pages, those pages are included once each at that number's position.")
    else:
        st.info("No pages matched yet. Correct the editable mapping table to generate the output PDF.")
else:
    st.info("Upload a PDF, enter your survey-number list, and click Analyze PDF pages to begin.")
