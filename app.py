import re, unicodedata, io
import pandas as pd
import streamlit as st
import pymupdf

st.set_page_config(page_title="PDF Survey Sequencer", layout="wide")
st.title("PDF Survey Sequencer")
st.write("Upload your PDF and paste the survey list. Output contains only matched/selected pages, in the exact pasted sequence.")

GUJ_DIGITS="૦૧૨૩૪૫૬૭૮૯"
ENG_DIGITS="0123456789"
DIGIT_TRANSLATION=str.maketrans(GUJ_DIGITS,ENG_DIGITS)

def to_ascii_digits(s):
    return str(s or "").translate(DIGIT_TRANSLATION)

def norm_key(value):
    s=to_ascii_digits(value)
    s=unicodedata.normalize("NFKC",s).lower()
    # Convert Gujarati Paiki and common written forms to p
    s=re.sub(r"પૈકી(?:નું)?|paiki|p\.?a\.?i\.?k\.?i\.?", "p",s,flags=re.I)
    s=re.sub(r"\bpart\b", "p", s, flags=re.I)
    # Keep numeric sequence and separators; strip unrelated words/labels
    s=re.sub(r"\s+","",s)
    s=re.sub(r"[^0-9p/.-]","",s)
    s=s.replace(".","/").replace("-","/")
    s=re.sub(r"/+","/",s)
    return s.strip("/")

def parse_list(raw):
    out=[]
    for line in raw.splitlines():
        for item in re.split(r"[,;]",line):
            item=item.strip()
            if item:
                k=norm_key(item)
                if k: out.append((item,k))
    return out

# Gujarati survey label and imperfect-text extraction variants seen in Gujarati PDF forms
LABEL_RE=re.compile(
    r"(બ્લોક\s*/?\s*(?:સરવે|સર્વે)|(?:સરવે|સર્વે)\s*(?:નંબર|નં\.?)|"
    r"survey\s*(?:no\.?|number)|block\s*(?:/|and)?\s*survey|block\s*(?:no\.?|number)|"
    r"લોક\s*/|ƞલોક\s*/|block/|survey)",
    re.I
)
NUMBER_LIKE_RE=re.compile(r"^[\s:：\-]*[0-9૦-૯]+(?:[./\-]\s*[0-9૦-૯]+)*(?:\s*(?:પૈકી|p|part)\s*[0-9૦-૯]+)*(?:\s*/\s*[0-9૦-૯]+)*[\s.)]*$",re.I)

def field_candidates(page_text):
    lines=[ln.strip() for ln in (page_text or "").splitlines() if ln.strip()]
    candidates=[]
    for idx,line in enumerate(lines):
        if LABEL_RE.search(line):
            # Value after label on same line if colon or dash separator exists.
            same=re.split(r"[:：]",line,maxsplit=1)
            if len(same)>1 and same[1].strip():
                candidates.append(same[1].strip())
            # Typical Gujarati form places survey value in next line(s).
            for nxt in lines[idx+1:idx+5]:
                if LABEL_RE.search(nxt):
                    break
                if NUMBER_LIKE_RE.match(nxt):
                    candidates.append(nxt.strip())
                    break
                # Some extraction formats contain extra punctuation; allow compact numeric-only line.
                compact=norm_key(nxt)
                if compact and re.fullmatch(r"[0-9p/]+",compact):
                    candidates.append(nxt.strip())
                    break
    # Remove duplicate candidates while retaining order
    seen=set(); cleaned=[]
    for c in candidates:
        k=norm_key(c)
        if k and k not in seen:
            cleaned.append((c,k)); seen.add(k)
    return cleaned

def page_index(doc):
    rows=[]
    for i,page in enumerate(doc):
        txt=page.get_text("text") or ""
        cand=field_candidates(txt)
        # Keep first candidate as primary but retain all candidates for matching/debug.
        rows.append({"PDF page":i+1,
                    "Field candidate(s)": " | ".join(c for c,k in cand) if cand else "FIELD NOT DETECTED",
                    "Survey key candidate(s)": " | ".join(k for c,k in cand) if cand else "",
                    "Text chars":len(txt),
                    "_keys":[k for c,k in cand]})
    return rows

def build_pdf(doc, selections):
    out=pymupdf.open()
    toc=[]
    for output_no,(list_row,raw,key,page_no) in enumerate(selections,1):
        out.insert_pdf(doc,from_page=page_no-1,to_page=page_no-1)
        toc.append([1,f"{raw} — source page {page_no}",output_no])
    if toc: out.set_toc(toc)
    data=out.tobytes(garbage=4,deflate=True)
    out.close()
    return data

pdf_upload=st.file_uploader("Step 1 — Upload original PDF",type=["pdf"])
list_text=st.text_area("Step 2 — Paste survey numbers in exact required order (one per line)",height=230,placeholder="25\n27\n30\n31\n44")
master=parse_list(list_text)

if pdf_upload and master:
    try:
        doc=pymupdf.open(stream=pdf_upload.getvalue(),filetype="pdf")
        st.info(f"PDF pages: {len(doc)} | Master list entries: {len(master)}")
        with st.spinner("Searching survey-number fields on each page..."):
            pindex=page_index(doc)

        key_pages={}
        for rec in pindex:
            for key in rec["_keys"]:
                key_pages.setdefault(key,[]).append(rec["PDF page"])

        rows=[]
        for i,(raw,key) in enumerate(master,1):
            pages=key_pages.get(key,[])
            rows.append({"List row":i,"Survey number":raw,"Normalized key":key,
                        "Auto-matched source page(s)":", ".join(map(str,pages)) if pages else "NOT FOUND",
                        "Source page to export":pages[0] if pages else None,
                        "Status":"Matched" if pages else "Not found"})
        match_df=pd.DataFrame(rows)
        nmatched=int((match_df.Status=="Matched").sum())
        st.subheader("Step 3 — Matching results")
        st.write(f"**Auto-matched entries: {nmatched} / {len(master)}**")
        st.dataframe(match_df[["List row","Survey number","Auto-matched source page(s)","Status"]],hide_index=True,use_container_width=True)

        with st.expander("Diagnostics: survey field text detected from each page"):
            diag=pd.DataFrame([{k:v for k,v in r.items() if k!="_keys"} for r in pindex])
            st.dataframe(diag,hide_index=True,use_container_width=True)
            st.caption("If field candidates are blank on most pages, this PDF may be image-scanned or the label text extraction is unusual.")

        st.subheader("Step 4 — Review / manually correct source page (if needed)")
        st.caption("Edit the source-page column for unmatched or incorrectly matched survey numbers. Leave blank to skip. Manual page number must be from the uploaded original PDF.")
        edit_df=match_df[["List row","Survey number","Source page to export"]].copy()
        edit_df["Source page to export"]=pd.to_numeric(edit_df["Source page to export"],errors="coerce")
        edited=st.data_editor(edit_df,hide_index=True,use_container_width=True,num_rows="fixed",key="survey_page_review_v3",
            column_config={
                "List row":st.column_config.NumberColumn(disabled=True),
                "Survey number":st.column_config.TextColumn(disabled=True),
                "Source page to export":st.column_config.NumberColumn(min_value=1,max_value=len(doc),step=1,help="Enter the original PDF page number for this survey. Leave blank to skip.")
            })

        final=[]
        skipped=[]
        for idx,(raw,key) in enumerate(master):
            v=edited.iloc[idx]["Source page to export"]
            page_no=None if pd.isna(v) else int(v)
            if page_no and 1<=page_no<=len(doc):
                final.append((idx+1,raw,key,page_no))
            else: skipped.append((idx+1,raw))

        st.subheader("Step 5 — Download the final sequenced PDF")
        if final:
            final_data=build_pdf(doc,final)
            st.success(f"PDF is ready: {len(final)} output pages. Extra/unselected pages are removed; order follows your list.")
            st.download_button("⬇️ Download FINAL Sequenced PDF",data=final_data,file_name="survey_pages_in_master_sequence.pdf",mime="application/pdf",type="primary",use_container_width=True)
        else:
            st.warning("No pages are matched/selected yet. Automatic matching has not found any pages. Use Step 4 to enter the original PDF page number for each survey number. The PDF download button becomes active after at least one page is selected.")

        if skipped:
            st.warning(f"{len(skipped)} list item(s) skipped (not found or no source page selected).")
            with st.expander("Skipped survey numbers"):
                st.dataframe(pd.DataFrame(skipped,columns=["List row","Survey number"]),hide_index=True)

        audit=match_df.copy()
        audit["Final source page"]=[None if pd.isna(v) else int(v) for v in edited["Source page to export"]]
        st.download_button("Download matching report (optional CSV)",audit.to_csv(index=False).encode("utf-8-sig"),"survey_matching_report.csv","text/csv")
        doc.close()
    except Exception as exc:
        st.error(f"PDF processing error: {exc}")
elif pdf_upload and not master:
    st.info("Paste the survey-number sequence to start matching.")
else:
    st.info("Upload a PDF and paste your sequence.")

st.divider()
st.caption("Matching uses searchable PDF text and the survey-number field. Image-only/scanned pages require Gujarati OCR, which is not included in this version.")
