import io
import re
import unicodedata
import hashlib
from collections import Counter

import fitz  # PyMuPDF
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Gujarati Survey Sequencer", page_icon="📑", layout="wide")

# ---------------------------- UI THEME (DESIGN ONLY) ----------------------------
CUSTOM_CSS = """
<style>
:root { --navy:#102A43; --blue:#2563EB; --teal:#0F766E; --ink:#1E293B; --muted:#64748B; --line:#E2E8F0; --surface:#FFFFFF; }
.stApp { background: linear-gradient(180deg, #F2F7FC 0%, #F8FAFC 260px, #F8FAFC 100%); color:var(--ink); }
.block-container { max-width: 1220px; padding-top: 1.65rem; padding-bottom: 3rem; }
[data-testid="stHeader"] { background: transparent; }
.hero { background:linear-gradient(125deg,#102A43 0%,#164E63 55%,#0F766E 100%); border-radius:22px; padding:26px 30px; color:#fff; box-shadow:0 12px 30px rgba(15,42,67,.13); margin-bottom:22px; }
.hero h1 { color:#fff !important; font-size:2rem !important; line-height:1.2; margin:0 0 8px 0; font-weight:750; }
.hero p { color:#D9EAF2 !important; margin:0; font-size:1rem; }
.hero-badge { display:inline-block; background:rgba(255,255,255,.13); border:1px solid rgba(255,255,255,.23); border-radius:999px; padding:5px 11px; margin-bottom:12px; font-size:.78rem; letter-spacing:.04em; }
.section-card { background:#fff; border:1px solid #E3EAF2; border-radius:18px; padding:18px 20px 12px; box-shadow:0 4px 14px rgba(15,42,67,.035); margin-bottom:14px; }
.section-head { display:flex; align-items:center; gap:11px; margin-bottom:12px; }
.step-pill { width:34px; height:34px; display:flex; align-items:center; justify-content:center; background:#E8F2FF; color:#1D4ED8; border-radius:11px; font-weight:800; }
.section-head h3 { margin:0; color:#102A43; font-size:1.15rem; }
.section-head small { color:#64748B; }
div[data-testid="stFileUploader"] { border:1.5px dashed #B8C9DB; background:#F8FBFF; border-radius:15px; padding:12px; }
div[data-testid="stTextArea"] textarea { border-radius:12px !important; background:#FBFDFF !important; font-family:ui-monospace, SFMono-Regular, Menlo, monospace !important; }
.stButton button, .stDownloadButton button { border-radius:12px !important; font-weight:700 !important; min-height:46px; }
.stDownloadButton button[kind="primary"] { background:linear-gradient(90deg,#0F766E,#0D9488) !important; border:0 !important; color:white !important; box-shadow:0 5px 14px rgba(13,148,136,.18); }
.stDownloadButton button[kind="primary"]:hover { background:#115E59 !important; }
div[data-testid="stMetric"] { background:#fff; border:1px solid #E2E8F0; border-radius:14px; padding:12px 15px; box-shadow:0 3px 10px rgba(15,42,67,.025); }
div[data-testid="stMetricLabel"] { color:#64748B; }
div[data-testid="stMetricValue"] { color:#102A43; }
div[data-testid="stAlert"] { border-radius:13px; }
hr { border-color:#E2E8F0; }
.footer { text-align:center; color:#94A3B8; font-size:.8rem; padding-top:20px; }
@media(max-width:700px){ .hero {padding:21px 19px;} .hero h1 {font-size:1.55rem !important;} .section-card {padding:14px;} }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

st.markdown(
    """
    <div class="hero">
      <span class="hero-badge">PDF AUTOMATION · LAND RECORDS</span>
      <h1>Gujarati Survey PDF Sequencer</h1>
      <p>Find only the current <b>બ્લોક સરવે નંબર</b> field, arrange matching pages in your exact list order, and download a clean PDF.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


GUJ_DIGITS = str.maketrans("૦૧૨૩૪૫૬૭૮૯", "0123456789")


def normalize_digits(text: str) -> str:
    return unicodedata.normalize("NFKC", (text or "").translate(GUJ_DIGITS))


def canonical_survey(text: str) -> str:
    """Normalize main and nested paiki/sub-survey paths to one slash path.

    Examples: 304/ પૈકી 2 -> 304/2; 306/paiki 1/paiki 1 -> 306/1/1.
    Repeated separators introduced by OCR or typed formats are collapsed.
    """
    text = normalize_digits(text).lower()
    text = re.sub(r"(?<=[0-9])પ(?=[0-9])", "5", text)  # common Gujarati OCR/list typo: પ for ૫
    text = text.replace("પૈકી", "/").replace("paiki", "/")
    text = re.sub(r"\s*[/.-]\s*", "/", text)
    text = re.sub(r"[^0-9/]", "", text)
    text = re.sub(r"/{2,}", "/", text)
    text = re.sub(r"^/+|/+$", "", text)
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
# Main number followed by any number of slash/paiki sub-number levels.
# Handles e.g. ૩૦૬/પૈકી ૧/પૈકી ૧ and ૩૯૦/૩/૨/પૈકી ૧.
NUMBER_RE = re.compile(
    r"[૦-૯0-9]{1,7}(?:\s*(?:[/.-]\s*(?:(?:પૈકી|paiki)\s*)?|(?:પૈકી|paiki)\s*)[૦-૯0-9]{1,5})*",
    re.I,
)


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


def render_target_region(page, scale=2.5):
    # Wider/taller crop than the speed-only build: include the current survey field
    # even if it is positioned lower on some scans. Still avoid full-page rendering.
    clip = fitz.Rect(0, 0, page.rect.width, page.rect.height * 0.62)
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip, alpha=False)
    from PIL import Image, ImageEnhance, ImageFilter
    image = Image.open(io.BytesIO(pix.tobytes("png"))).convert("L")
    image = ImageEnhance.Contrast(image).enhance(1.6)
    image = ImageEnhance.Sharpness(image).enhance(1.4)
    return image


def run_ocr(image, pytesseract):
    # Accuracy-first retries: alternate segmentation and binarized image, only
    # when the first OCR pass cannot read the target field/value.
    try:
        first = pytesseract.image_to_string(image, lang="guj+eng", config="--psm 6")
        if get_value_after_label(first):
            return first, ""
        second = pytesseract.image_to_string(image, lang="guj+eng", config="--psm 11")
        if get_value_after_label(second):
            return first + "\n" + second, ""
        return first + "\n" + second, ""
    except Exception as err:
        return "", str(err)


def targeted_retry(page, pytesseract, desired_keys):
    """High-quality retry; prefer OCR pass that reads an exact unresolved key."""
    clip = fitz.Rect(0, 0, page.rect.width, page.rect.height * 0.72)
    pix = page.get_pixmap(matrix=fitz.Matrix(3, 3), clip=clip, alpha=False)
    from PIL import Image, ImageOps, ImageEnhance, ImageFilter
    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("L")
    img = ImageOps.autocontrast(img)
    img = ImageEnhance.Contrast(img).enhance(1.8)
    img = img.filter(ImageFilter.MedianFilter(size=3))
    outputs = []
    for psm in (11, 6):
        outputs.append(pytesseract.image_to_string(img, lang="guj+eng", config=f"--psm {psm}"))
    binary = img.point(lambda pixel: 255 if pixel > 155 else 0)
    outputs.append(pytesseract.image_to_string(binary, lang="guj+eng", config="--psm 6"))
    values = [get_value_after_label(out) for out in outputs]
    desired = set(desired_keys)
    for value in values:
        if canonical_survey(value or "") in desired:
            return "\n--- retry pass ---\n".join(outputs), value
    # Only use a fallback OCR value if it differs from the previous misread.
    for value in values:
        if value:
            return "\n--- retry pass ---\n".join(outputs), value
    return "\n--- retry pass ---\n".join(outputs), None



def scan_pdf(pdf_bytes: bytes, ocr_enabled: bool, progress_bar, progress_text):
    """Scan PDF with a visible progress indicator; OCR retry only if needed."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        detected, diagnostics = [], []
        ocr_engine = None
        ocr_langs = []
        if ocr_enabled:
            try:
                import pytesseract as _pytesseract
                ocr_engine = _pytesseract
                ocr_langs = _pytesseract.get_languages(config="")
            except Exception:
                ocr_engine = None

        page_count = len(doc)
        for page_idx, page in enumerate(doc):
            percent = int(page_idx * 100 / max(1, page_count))
            progress_text.markdown(f"**Scanning: {percent}%** · Page {page_idx + 1}/{page_count}")
            progress_bar.progress(page_idx / max(1, page_count))
            text_page = page.get_text("text") or ""
            survey = get_value_after_label(text_page)
            method = "PDF embedded text — current field"
            ocr_preview = ""
            if not survey and ocr_enabled:
                if ocr_engine is None:
                    method = "OCR not installed"
                elif "guj" not in ocr_langs:
                    method = "Gujarati OCR language pack missing (guj)"
                else:
                    try:
                        crop = render_target_region(page, scale=2.5)
                        ocr_preview, ocr_err = run_ocr(crop, ocr_engine)
                        if ocr_err:
                            method = "OCR error: " + ocr_err[:140]
                        else:
                            survey = get_value_after_label(ocr_preview)
                            method = "Gujarati OCR — wider upper field crop" if survey else "OCR retries exhausted — target field/value not read"
                    except Exception as exc:
                        method = "OCR failed: " + str(exc)[:140]
            detected.append(survey)
            diagnostics.append({
                "PDF page": page_idx + 1,
                "Current Block Survey Number detected": survey or "Not detected",
                "Method": method,
                "Target-field OCR text (only crop)": (ocr_preview or "")[:450],
            })
            progress_bar.progress((page_idx + 1) / max(1, page_count))
            progress_text.markdown(f"**Scanning: {int((page_idx + 1) * 100 / max(1, page_count))}%** · Page {page_idx + 1}/{page_count}")
        return detected, diagnostics
    finally:
        doc.close()


# ------------------------------- MAIN WORKFLOW --------------------------------
left, right = st.columns([1.05, 1], gap="large")
with left:
    st.markdown('<div class="section-card"><div class="section-head"><div class="step-pill">1</div><div><h3>Upload original PDF</h3><small>Choose the source land-record PDF</small></div></div>', unsafe_allow_html=True)
    pdf_upload = st.file_uploader("Source PDF", type=["pdf"], label_visibility="collapsed")
    if pdf_upload:
        st.caption(f"📄 {pdf_upload.name} · {pdf_upload.size/1024:,.0f} KB")
    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown('<div class="section-card"><div class="section-head"><div class="step-pill">2</div><div><h3>Paste survey sequence</h3><small>One number per line; order is preserved</small></div></div>', unsafe_allow_html=True)
    sequence_input = st.text_area(
        "Survey sequence", height=210, label_visibility="collapsed",
        placeholder="૧૬૨\n૧૬૪\n૧૬૫\n૧૬૯\n૧૭૪\n…",
    )
    st.caption("Gujarati or English digits supported · duplicate entries preserved")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="section-card"><div class="section-head"><div class="step-pill">3</div><div><h3>Processing settings</h3><small>OCR fallback for scanned/image PDFs</small></div></div>', unsafe_allow_html=True)
ocr_on = st.checkbox("Enable Gujarati OCR fallback", value=True, help="Use Gujarati+English OCR if embedded PDF text does not identify the current survey-number field.")
st.markdown("</div>", unsafe_allow_html=True)

if pdf_upload and sequence_input.strip():
    requested = parse_sequence(sequence_input)
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

    st.markdown('<div class="section-card"><div class="section-head"><div class="step-pill">4</div><div><h3>Detection & results</h3><small>Reading only the current Block Survey Number field</small></div></div>', unsafe_allow_html=True)
    pdf_bytes = pdf_upload.getvalue()
    cache_key = hashlib.sha256(pdf_bytes + (b"OCR_ON" if ocr_on else b"OCR_OFF")).hexdigest()
    if st.session_state.get("survey_scan_cache_key") == cache_key:
        detected, diagnostics = st.session_state["survey_scan_cache"]
        st.info("Using saved scan results for this PDF — no repeat OCR scan.")
    else:
        progress_text = st.empty()
        progress_bar = st.progress(0)
        detected, diagnostics = scan_pdf(pdf_bytes, ocr_on, progress_bar, progress_text)
        st.session_state["survey_scan_cache_key"] = cache_key
        st.session_state["survey_scan_cache"] = (detected, diagnostics)
        progress_text.markdown("**Scanning: 100% · Complete**")
        progress_bar.progress(1.0)

    # If requested paiki numbers are missing, selectively retry likely pages:
    # same main survey number or pages where the current field was not detected.
    def main_survey(key):
        return (key or "").split("/", 1)[0]
    missing_before_retry = [key for key in requested if key not in [canonical_survey(v or "") for v in detected]]
    retry_pages = set()
    if missing_before_retry and ocr_on:
        try:
            import pytesseract as retry_ocr
            retry_langs = retry_ocr.get_languages(config="")
            if "guj" in retry_langs:
                target_bases = {main_survey(k) for k in missing_before_retry}
                for idx, found in enumerate(detected):
                    found_key = canonical_survey(found or "")
                    if (not found_key) or (main_survey(found_key) in target_bases):
                        retry_pages.add(idx)
                if retry_pages:
                    retry_status = st.empty()
                    retry_progress = st.progress(0)
                    source_retry_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                    try:
                        for count, page_idx in enumerate(sorted(retry_pages), start=1):
                            retry_status.markdown(f"**Accuracy retry: {int(count*100/len(retry_pages))}%** · Rechecking page {page_idx+1}")
                            retry_progress.progress(count / len(retry_pages))
                            retry_text, retry_value = targeted_retry(source_retry_doc[page_idx], retry_ocr, missing_before_retry)
                            # Replace only when retry reads a value; never erase a prior detection.
                            if retry_value:
                                detected[page_idx] = retry_value
                                diagnostics[page_idx]["Current Block Survey Number detected"] = retry_value
                                diagnostics[page_idx]["Method"] = "Targeted OCR accuracy retry"
                                diagnostics[page_idx]["Target-field OCR text (only crop)"] = retry_text[:450]
                    finally:
                        source_retry_doc.close()
                    retry_status.markdown("**Accuracy retry: complete**")
        except Exception as retry_exc:
            st.warning(f"Targeted OCR retry was not available: {retry_exc}")

    # Store final detections after selective accuracy retries as well, so later
    # UI reruns reuse the corrected page values instead of OCRing them again.
    st.session_state["survey_scan_cache_key"] = cache_key
    st.session_state["survey_scan_cache"] = (detected, diagnostics)

    matches, missing, used_pages = [], [], set()
    for survey in requested:
        page_i = next((i for i, found in enumerate(detected) if i not in used_pages and canonical_survey(found or "") == survey), None)
        if page_i is None:
            missing.append(survey)
        else:
            used_pages.add(page_i)
            matches.append((survey, page_i))

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown('<div class="section-card"><div class="section-head"><div class="step-pill">5</div><div><h3>Sequenced PDF</h3><small>Only matched pages · exact master-list order</small></div></div>', unsafe_allow_html=True)
    m1, m2, m3 = st.columns(3)
    m1.metric("Requested numbers", len(requested))
    m2.metric("Matched pages", len(matches))
    m3.metric("Not found", len(missing))
    if missing:
        st.warning("Not found in the current `બ્લોક સરવે નંબર` field: " + ", ".join(missing))
    with st.expander("Page-by-page detection diagnostics", expanded=(not matches)):
        st.dataframe(pd.DataFrame(diagnostics), use_container_width=True, hide_index=True)

    if matches:
        output = fitz.open()
        for survey, page_i in matches:
            output.insert_pdf(source_doc, from_page=page_i, to_page=page_i)
        output_bytes = output.tobytes(garbage=4, deflate=True)
        output.close()
        st.success(f"Ready: {len(matches)} sequenced pages. Extra pages excluded; requested order preserved.")
        st.download_button(
            "⬇️ DOWNLOAD SEQUENCED PDF",
            data=output_bytes,
            file_name="survey_pages_in_requested_sequence.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True,
        )
        report = pd.DataFrame([{"Requested Survey": s, "Original PDF Page": p + 1} for s, p in matches])
        st.download_button("Download optional match report (CSV)", data=report.to_csv(index=False).encode("utf-8-sig"), file_name="survey_match_report.csv", mime="text/csv")
    else:
        st.error("No pages matched the CURRENT `બ્લોક સરવે નંબર` field. The PDF download is unavailable until a match is found; CSV is only an optional diagnostic.")
        st.button("⬇️ DOWNLOAD SEQUENCED PDF", disabled=True, type="primary", use_container_width=True)
        st.download_button("Download optional diagnostics CSV", data=pd.DataFrame(diagnostics).to_csv(index=False).encode("utf-8-sig"), file_name="target_field_diagnostics.csv", mime="text/csv")
    st.markdown("</div>", unsafe_allow_html=True)
else:
    st.markdown('<div class="section-card"><div class="section-head"><div class="step-pill">4</div><div><h3>Ready when you are</h3><small>Upload a PDF and paste your sequence to start</small></div></div>', unsafe_allow_html=True)
    st.info("Your source PDF is kept as the input. The final file will contain only matching survey pages, in your exact requested order.")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="footer">Gujarati Survey PDF Sequencer · Current survey field only · Extra pages excluded</div>', unsafe_allow_html=True)
