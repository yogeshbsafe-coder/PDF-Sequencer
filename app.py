import io
import re
import unicodedata
from collections import Counter

import fitz  # PyMuPDF
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Gujarati Survey PDF Sequencer", layout="wide")
st.title("Gujarati Survey PDF Sequencer")
st.markdown(
    "Reads **only the current `બ્લોક સરવે નંબર` field** (not જૂનો બ્લોક/સરવે નંબર, " 
    "not other numbers), then creates a new PDF containing only requested survey pages "
    "in the exact order of your list."
)

GUJ_DIGITS = str.maketrans("૦૧૨૩૪૫૬૭૮૯", "0123456789")


def normalize_digits(text: str) -> str:
    return unicodedata.normalize("NFKC", (text or "").translate(GUJ_DIGITS))


def canonical_survey(text: str) -> str:
    """Normalize a survey value only; preserve sub-number separators as slash."""
    text = normalize_digits(text).lower()
    text = text.replace("પૈકી", "/").replace("paiki", "/")
    text = re.sub(r"\\s*[/.-]\\s*", "/", text)
    text = re.sub(r"[^0-9/]", "", text)
    text = re.sub(r"/+$", "", text)
    return text


def parse_sequence(raw: str):
    items = []
    for line in re.split(r"[\n,;]+", normalize_digits(raw)):
        item = line.strip()
        if not item:
            continue
        item = re.sub(r"\s*(?:પૈકી|paiki)\s*", "/", item, flags=re.I)
        key = canonical_survey(item)
        if key:
            items.append(key)  # duplicates intentionally preserved
    return items


# Narrow label: current Block Survey Number only. Explicitly exclude old-survey label.
CURRENT_LABEL_RE = re.compile(
    r"(?<!જૂનો\s)(?:બ્લોક\s*[/]?\s*સરવે\s*નંબર|બ્લોક\s*[/]?\s*સર્વે\s*નંબર|"
    r"બ્લોક\s*સરવે\s*નં?\s*|બ્લોક\s*સર્વે\s*નં?\s*)",
    re.I,
)
NUMBER_RE = re.compile(r"[૦-૯0-9]{1,7}(?:\s*[/.-]\s*[૦-૯0-9]{1,5})?(?:\s*(?:પૈકી|paiki)\s*[૦-૯0-9]{1,5})?", re.I)


def get_value_after_label(text: str):
    """Extract a value only from a line containing the target current-field label."""
    if not text:
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for i, line in enumerate(lines):
        # Old survey field is ignored even if OCR happens to include the target words.
        if "જૂનો" in line or "જુનો" in line:
            continue
        m = CURRENT_LABEL_RE.search(line)
        if not m:
            continue
        tail = line[m.end():]
        tail = re.sub(r"^[\s:：#№-]+", "", tail)
        nm = NUMBER_RE.search(tail)
        if nm:
            return canonical_survey(nm.group(0)) or None
        # Field value can wrap to the next line; inspect only next line, not other fields.
        if i + 1 < len(lines):
            next_line = lines[i + 1]
            if "જૂનો" not in next_line and "જુનો" not in next_line:
                nm = NUMBER_RE.search(next_line)
                if nm:
                    return canonical_survey(nm.group(0)) or None
    return None


def render_target_region(page, scale=3):
    # Field is in the upper form area in the supplied land-record layout.
    # OCR is restricted to the top 52% of the page to avoid unrelated lower-page content.
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    from PIL import Image
    image = Image.open(io.BytesIO(pix.tobytes("png")))
    w, h = image.size
    return image.crop((0, 0, w, int(h * 0.52)))


def run_ocr(image, pytesseract):
    # Gujarati+English OCR only on the crop where the target field is expected.
    attempts = []
    for psm in (6, 11, 4):
        try:
            attempts.append(pytesseract.image_to_string(image, lang="guj+eng", config=f"--psm {psm}"))
        except Exception as err:
            return "", str(err)
    return "\n".join(attempts), ""


pdf_upload = st.file_uploader("Upload the original PDF", type=["pdf"])
sequence_input = st.text_area(
    "Survey number sequence (one per line; Gujarati or English digits; order preserved)",
    height=230,
    placeholder="૧૬૨\n૧૬૪\n૧૬૫\n૧૬૯\n૧૭૪\n...",
)
ocr_on = st.checkbox("Gujarati OCR fallback (for scanned PDFs)", value=True)

if pdf_upload and sequence_input.strip():
    requested = parse_sequence(sequence_input)
    st.caption(f"Parsed sequence: {len(requested)} items. Duplicates are preserved.")
    try:
        source_doc = fitz.open(stream=pdf_upload.getvalue(), filetype="pdf")
    except Exception as exc:
        st.error(f"Could not open PDF: {exc}")
        st.stop()

    pytesseract = None
    ocr_langs = []
    if ocr_on:
        try:
            import pytesseract
            ocr_langs = pytesseract.get_languages(config="")
        except Exception:
            pytesseract = None

    detected = []
    diagnostics = []
    prog = st.progress(0, text="Reading current Block Survey Number field only…")
    for page_index, page in enumerate(source_doc):
        text_page = page.get_text("text") or ""
        survey = get_value_after_label(text_page)
        method = "PDF embedded text — target field"
        ocr_preview = ""
        if not survey and ocr_on:
            if pytesseract is None:
                method = "OCR not installed"
            elif "guj" not in ocr_langs:
                method = "Gujarati OCR language pack missing (guj)"
            else:
                try:
                    crop = render_target_region(page, scale=3)
                    ocr_preview, ocr_err = run_ocr(crop, pytesseract)
                    if ocr_err:
                        method = "OCR error: " + ocr_err[:140]
                    else:
                        survey = get_value_after_label(ocr_preview)
                        method = "Gujarati OCR — upper field crop" if survey else "OCR attempted — current label/value not read"
                except Exception as exc:
                    method = "OCR failed: " + str(exc)[:140]
        detected.append(survey)
        diagnostics.append({
            "PDF page": page_index + 1,
            "Current Block Survey Number detected": survey or "Not detected",
            "Method": method,
            "Target-field OCR text (only crop)": (ocr_preview or "")[:300],
        })
        prog.progress((page_index + 1) / max(1, len(source_doc)), text=f"Checking page {page_index+1}/{len(source_doc)}")
    prog.empty()

    # Master list order is authoritative. A PDF page can be used only once; duplicates in
    # the master list are retained if there are multiple pages carrying the same number.
    matches, missing, used_pages = [], [], set()
    for survey in requested:
        page_i = next((i for i, found in enumerate(detected) if i not in used_pages and canonical_survey(found or "") == survey), None)
        if page_i is None:
            missing.append(survey)
        else:
            used_pages.add(page_i)
            matches.append((survey, page_i))

    st.subheader("Matching summary")
    st.write(f"Requested: **{len(requested)}** · Matched pages: **{len(matches)}** · Not found: **{len(missing)}**")
    if missing:
        st.warning("Not found in the current Block Survey Number field: " + ", ".join(missing))
    with st.expander("Page-by-page target-field diagnostics", expanded=(not matches)):
        st.dataframe(pd.DataFrame(diagnostics), use_container_width=True, hide_index=True)

    # The PDF output button is always shown; when no pages match, it is disabled with an
    # explicit explanation, not replaced by a CSV-only download.
    if matches:
        output = fitz.open()
        for survey, page_i in matches:
            output.insert_pdf(source_doc, from_page=page_i, to_page=page_i)
        output_bytes = output.tobytes(garbage=4, deflate=True)
        output.close()
        st.success(f"Created sequenced PDF: {len(matches)} pages. Extra pages excluded; requested order preserved.")
        st.download_button(
            "⬇️ DOWNLOAD SEQUENCED PDF",
            data=output_bytes,
            file_name="survey_pages_in_requested_sequence.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True,
        )
        report = pd.DataFrame([{"Requested Survey": s, "Original PDF Page": p + 1} for s, p in matches])
        st.download_button("Optional match report (CSV)", data=report.to_csv(index=False).encode("utf-8-sig"), file_name="survey_match_report.csv", mime="text/csv")
    else:
        st.error("No pages matched the CURRENT `બ્લોક સરવે નંબર` field. The PDF download is unavailable until a match is found; CSV is only an optional diagnostic.")
        st.button("⬇️ DOWNLOAD SEQUENCED PDF", disabled=True, type="primary", use_container_width=True)
        st.download_button("Optional diagnostics CSV", data=pd.DataFrame(diagnostics).to_csv(index=False).encode("utf-8-sig"), file_name="target_field_diagnostics.csv", mime="text/csv")
else:
    st.info("Upload a PDF and paste the sequence. The tool will read only the current `બ્લોક સરવે નંબર` field and create a PDF in your exact order.")
