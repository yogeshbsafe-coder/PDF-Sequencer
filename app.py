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

st.set_page_config(page_title="PDF Survey Sequencer & Editor", page_icon="📄", layout="wide")
st.title("📄 PDF Survey Sequencer & Survey Number Editor")
st.write("Arrange PDF pages according to your master survey list, review detected numbers, and optionally correct the printed ‘બ્લોક/સરવે નંબર :’ value on each page.")

GUJ_DIGITS = str.maketrans("૦૧૨૩૪૫૬૭૮૯", "0123456789")
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

def normalize(value):
    value = str(value or "").translate(GUJ_DIGITS).translate(ARABIC_DIGITS).strip()
    return re.sub(r"\s+", "", value)

def gujarati_digits(value):
    return str(value).translate(str.maketrans("0123456789", "૦૧૨૩૪૫૬૭૮૯"))

def parse_list(raw):
    parts = re.split(r"[,;\n]+", raw or "")
    out = []
    for part in parts:
        v = normalize(part)
        if v and v not in out:
            out.append(v)
    return out

def extract_text(page):
    try: return page.get_text("text") or ""
    except Exception: return ""

def run_ocr(page):
    if not OCR_AVAILABLE: return ""
    try:
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        try: return pytesseract.image_to_string(img, lang="eng+guj")
        except Exception: return pytesseract.image_to_string(img, lang="eng")
    except Exception: return ""

def number_candidates(text):
    text = text.translate(GUJ_DIGITS).translate(ARABIC_DIGITS)
    vals = re.findall(r"(?<![\w])\d+(?:[./-]\d+)*(?![\w])", text)
    return list(dict.fromkeys(normalize(v) for v in vals if normalize(v)))

def preview(page):
    return page.get_pixmap(matrix=fitz.Matrix(1.25, 1.25), alpha=False).tobytes("png")

def text_safe(v):
    return "" if pd.isna(v) else str(v)

def replace_text_value(page, old, new):
    """Replace occurrences of a searchable old value. Scanned-only text cannot be replaced automatically."""
    old, new = normalize(old), str(new).strip()
    if not old or not new or old == normalize(new):
        return 0, "No replacement needed"
    # Search numeric forms including Gujarati and Latin digit variants.
    search_forms = list(dict.fromkeys([old, gujarati_digits(old)]))
    rects = []
    for form in search_forms:
        try:
            rects.extend(page.search_for(form))
        except Exception:
            pass
    # deduplicate rectangles
    unique = []
    for r in rects:
        if not any(abs(r.x0-q.x0)<1 and abs(r.y0-q.y0)<1 and abs(r.x1-q.x1)<1 and abs(r.y1-q.y1)<1 for q in unique):
            unique.append(r)
    if not unique:
        return 0, "Not found as selectable text (scanned/OCR PDF or different printed format)"
    for r in unique:
        page.add_redact_annot(r, fill=(1,1,1))
    page.apply_redactions()
    for r in unique:
        # Slightly inset to reduce risk of text clipping outside the original number field.
        box = fitz.Rect(r.x0, r.y0-0.2, r.x1+max(1, r.width*0.1), r.y1+0.3)
        fontsize = max(6, min(12, r.height*0.82))
        # Try the available font size and shrink if text doesn't fit.
        for fs in range(int(fontsize), 4, -1):
            try:
                result = page.insert_textbox(box, new, fontsize=fs, fontname="helv", color=(0,0,0), align=0)
                if result >= 0: break
            except Exception: pass
    return len(unique), "Replaced selectable text"

uploaded = st.file_uploader("Upload original PDF", type=["pdf"])
if uploaded:
    pdf_bytes = uploaded.getvalue()
    try: doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        st.error(f"PDF could not be opened: {e}"); st.stop()
    st.success(f"Loaded {len(doc)} pages")
    master = st.text_area("Paste master survey-number list in the required order", placeholder="Example: 12\n12/1\n13\n14\n25/2", height=160)
    desired = parse_list(master)
    use_ocr = st.checkbox("Try OCR on pages with little selectable text", value=True)
    if use_ocr and not OCR_AVAILABLE:
        st.warning("OCR support is unavailable in this deployment. Text extraction will still work.")
    if st.button("Analyze PDF and detect survey numbers", type="primary", disabled=not desired):
        rows=[]
        progress=st.progress(0)
        for i,p in enumerate(doc):
            txt=extract_text(p); ocr=False
            if use_ocr and len(txt.strip())<25 and OCR_AVAILABLE:
                o=run_ocr(p)
                if o.strip(): txt += "\n"+o; ocr=True
            cand=number_candidates(txt)
            # Suggest only a master-list number found on page. Otherwise keep a blank for manual mapping.
            found=[x for x in cand if x in desired]
            rows.append({"PDF Page":i+1,"Survey number assigned (edit)":", ".join(found),
                        "Printed number to replace (optional)":"","Replace with (optional)":"",
                        "Detected candidates":", ".join(cand),"OCR used":"Yes" if ocr else "No",
                        "Page text sample":txt[:1800]})
            progress.progress((i+1)/len(doc))
        st.session_state.seq_rows=rows
        st.session_state.seq_wanted=desired
        st.session_state.seq_pdf=pdf_bytes
        st.session_state.seq_filename=uploaded.name
        st.success("Detection finished. Review and edit the mapping below before creating the final PDF.")

if "seq_rows" in st.session_state:
    rows=st.session_state.seq_rows; desired=st.session_state.seq_wanted; pdf_bytes=st.session_state.seq_pdf
    st.header("Step 2 — Review page mapping and correction fields")
    st.info("Correct the ‘Survey number assigned’ column so each source page maps to the number in your master list. Optional replacement fields let you update the printed number on that page: enter the old printed number and the corrected number. Only selectable PDF text can be replaced automatically; scanned text is reported as not replaceable.")
    df=pd.DataFrame(rows)
    edited=st.data_editor(df[["PDF Page","Survey number assigned (edit)","Printed number to replace (optional)","Replace with (optional)","Detected candidates","OCR used"]],
        hide_index=True, width="stretch", num_rows="fixed",
        disabled=["PDF Page","Detected candidates","OCR used"],
        column_config={
            "Survey number assigned (edit)":st.column_config.TextColumn(help="Page's mapping number; use exact master-list value. Multiple values comma-separated."),
            "Printed number to replace (optional)":st.column_config.TextColumn(help="Old value printed on page. Leave blank if no edit is required."),
            "Replace with (optional)":st.column_config.TextColumn(help="New value to print over old value. Leave blank if no edit is required."),
        })
    with st.expander("Preview source page / extracted text"):
        sel=st.selectbox("Page number",range(1,len(doc)+1))
        st.image(preview(doc[sel-1]),caption=f"Source PDF page {sel}")
        st.text_area("Extracted page text", rows[sel-1]["Page text sample"],height=140,disabled=True)

    map_pages=defaultdict(list)
    replacement_by_page={}
    for _,r in edited.iterrows():
        pg=int(r["PDF Page"])
        for x in re.split(r"[,;\n]+",text_safe(r["Survey number assigned (edit)"])):
            k=normalize(x)
            if k: map_pages[k].append(pg)
        old=normalize(r["Printed number to replace (optional)"])
        new=text_safe(r["Replace with (optional)"]).strip()
        if old and new: replacement_by_page[pg]=(old,new)

    ordered_pages=[]; matched=[]; missing=[]
    for number in desired:
        pgs=map_pages.get(number,[])
        if pgs:
            matched.append((number,pgs))
            for p in pgs:
                if p not in ordered_pages: ordered_pages.append(p)
        else: missing.append(number)
    mapped=set(map_pages); extra=sorted(mapped-set(desired)); skipped=sorted(set(range(1,len(doc)+1))-set(ordered_pages))
    st.header("Step 3 — Results")
    m1,m2,m3,m4=st.columns(4)
    m1.metric("PDF pages",len(doc));m2.metric("Output pages",len(ordered_pages));m3.metric("Missing list items",len(missing));m4.metric("Skipped pages",len(skipped))
    if matched:
        st.subheader("Master list → source page(s)")
        st.dataframe(pd.DataFrame([{"Survey number":n,"Source page(s)":", ".join(map(str,ps))} for n,ps in matched]),hide_index=True,width="stretch")
    left,right=st.columns(2)
    with left:
        st.subheader("Missing from PDF / mapping")
        if missing: st.dataframe(pd.DataFrame({"Missing number":missing}),hide_index=True)
        else: st.success("All master-list entries are mapped.")
    with right:
        st.subheader("Mapped but not in master list")
        if extra: st.dataframe(pd.DataFrame({"Extra mapped number":extra}),hide_index=True)
        else: st.success("No extra mapped numbers.")
    if skipped: st.caption("Skipped source pages: "+", ".join(map(str,skipped)))

    if ordered_pages:
        if st.button("Build final PDF (sequence + optional number corrections)",type="primary"):
            source=fitz.open(stream=pdf_bytes,filetype="pdf")
            out=fitz.open(); correction_log=[]
            for page_num in ordered_pages:
                page=source[page_num-1]
                if page_num in replacement_by_page:
                    old,new=replacement_by_page[page_num]
                    count,status=replace_text_value(page,old,new)
                    correction_log.append({"Page":page_num,"Old value":old,"New value":new,"Occurrences":count,"Status":status})
                out.insert_pdf(source,from_page=page_num-1,to_page=page_num-1)
            final_bytes=out.tobytes(garbage=4,deflate=True)
            st.session_state.final_pdf=final_bytes
            st.session_state.correction_log=correction_log
            out.close();source.close()
            st.success("Final PDF created. Review the correction report below before downloading.")
    if "final_pdf" in st.session_state:
        st.download_button("Download final sequenced PDF",data=st.session_state.final_pdf,file_name="survey_numbers_corrected_sequenced.pdf",mime="application/pdf")
        logs=st.session_state.get("correction_log",[])
        if logs:
            st.subheader("Survey-number correction report")
            st.dataframe(pd.DataFrame(logs),hide_index=True,width="stretch")
            csv=pd.DataFrame(logs).to_csv(index=False).encode("utf-8-sig")
            st.download_button("Download correction report CSV",csv,"survey_correction_report.csv","text/csv")
        else:
            st.caption("No optional text corrections were entered. PDF is reordered only.")
else:
    st.info("Upload your PDF, paste your list, and analyze the pages to get started.")
