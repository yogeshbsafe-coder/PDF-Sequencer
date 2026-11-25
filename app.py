import re
import unicodedata
import pandas as pd
import streamlit as st
import pymupdf

st.set_page_config(page_title="PDF Survey Sequencer", layout="wide")
st.title("PDF Survey Sequencer")
st.markdown("**Goal:** Export only pages matching your survey-number list, in the exact list order. Unwanted/extra pages are excluded.")

GUJ_DIGITS="૦૧૨૩૪૫૬૭૮૯"
ENG_DIGITS="0123456789"
TRANS=str.maketrans(GUJ_DIGITS, ENG_DIGITS)

def digits(s):
    return str(s or "").translate(TRANS)

def clean_number(s):
    s=digits(s)
    s=unicodedata.normalize("NFKC",s).lower()
    s=s.replace("પૈકી","p").replace("paiki","p")
    s=re.sub(r"(?i)\bpart\b","p",s)
    s=re.sub(r"\s+","",s)
    s=re.sub(r"[^0-9p/.-]","",s)
    s=s.replace(".","/").replace("-","/")
    s=re.sub(r"/+","/",s)
    return s.strip("/")

def parse_master(text):
    items=[]
    for line in (text or "").splitlines():
        for part in re.split(r"[,;]",line):
            raw=part.strip()
            key=clean_number(raw)
            if key:
                items.append((raw,key))
    return items

# Label-first extraction: only take number-like text adjacent to survey-field label.
LABELS=[
    r"બ્લોક\s*/?\s*સરવે\s*\(?સર્વે\)?\s*નંબર",
    r"બ્લોક\s*/?\s*(?:સરવે|સર્વે)\s*(?:નં|નંબર)?",
    r"(?:સરવે|સર્વે)\s*(?:નંબર|નં\.?|no\.?)",
    r"survey\s*(?:number|no\.?)",
    r"block\s*/?\s*survey",
    r"block\s*(?:number|no\.?)",
]
LABEL_RE=re.compile("|".join(LABELS), re.I)

def numeric_candidate(text):
    # Normalize Gujarati digits; retain paiki notation and slash/dot/dash.
    s=digits(text).replace("પૈકી","p").replace("paiki","p")
    s=re.sub(r"(?i)\bpart\b","p",s)
    s=re.sub(r"\s+","",s)
    # Accept number with optional sub-part, and reject if text contains unrelated alphabetic words.
    s=re.sub(r"[^0-9p/.-]","",s).replace(".","/").replace("-","/")
    s=re.sub(r"/+","/",s).strip("/")
    return s if re.fullmatch(r"[0-9]+(?:p[0-9]+|/[0-9]+|p)?(?:/[0-9]+)*",s) else ""

def get_field_candidates(text):
    lines=[x.strip() for x in (text or "").splitlines() if x.strip()]
    found=[]
    for i,line in enumerate(lines):
        m=LABEL_RE.search(line)
        if not m: continue
        # Value after label on same line (prefer after colon)
        tail=line[m.end():].strip(" :：.-")
        if tail:
            cand=numeric_candidate(tail)
            if cand: found.append(cand)
        # Some forms put field value on following line; look at a short neighborhood
        for j in range(i+1,min(i+4,len(lines))):
            nxt=lines[j]
            if LABEL_RE.search(nxt): break
            cand=numeric_candidate(nxt)
            if cand:
                found.append(cand)
                break
    # retain unique candidates
    return list(dict.fromkeys(clean_number(x) for x in found if clean_number(x)))

def scan_pages(doc):
    page_info=[]
    for pno,page in enumerate(doc,1):
        text=page.get_text("text") or ""
        candidates=get_field_candidates(text)
        page_info.append({"page":pno,"field_candidates":candidates,"text":text})
    return page_info

def make_output_pdf(doc, rows):
    out=pymupdf.open()
    for row in rows:
        pno=int(row["source_page"])
        out.insert_pdf(doc,from_page=pno-1,to_page=pno-1)
    blob=out.tobytes(garbage=4,deflate=True)
    out.close()
    return blob

uploaded=st.file_uploader("1) Upload original PDF",type=["pdf"])
sequence_text=st.text_area("2) Paste survey numbers in your required sequence (one number per line)",height=230,
    placeholder="162\n164\n165\n169\n174\n175\n293\n294\n295\n299\n300\n305\n310\n311\n319\n320\n1\n159\n161\n227\n228\n641\n642")
master=parse_master(sequence_text)

if uploaded and master:
    try:
        doc=pymupdf.open(stream=uploaded.getvalue(),filetype="pdf")
        st.success(f"Loaded PDF: {len(doc)} pages | Requested survey entries: {len(master)}")
        with st.spinner("Scanning PDF pages for survey-number field..."):
            page_info=scan_pages(doc)
        key_to_pages={}
        for page in page_info:
            for key in page["field_candidates"]:
                key_to_pages.setdefault(key,[]).append(page["page"])

        initial_rows=[]
        for i,(raw,key) in enumerate(master,1):
            matches=key_to_pages.get(key,[])
            initial_rows.append({
                "List position":i,
                "Survey number":raw,
                "Detected source page(s)":", ".join(map(str,matches)) if matches else "Not detected",
                "Choose original PDF page":matches[0] if matches else None,
                "Match status":"Found" if matches else "Not found",
            })
        df=pd.DataFrame(initial_rows)
        st.subheader("3) Survey-number matching")
        st.write(f"Detected {sum(r['Match status']=='Found' for r in initial_rows)} of {len(master)} entries.")
        st.dataframe(df[["List position","Survey number","Detected source page(s)","Match status"]],hide_index=True,use_container_width=True)

        with st.expander("Diagnostic: what survey field was read from each PDF page"):
            diagnostic=pd.DataFrame([{"Original PDF page":p["page"],"Survey field candidate(s)":", ".join(p["field_candidates"]) or "No field detected","Extracted text preview":p["text"][:500]} for p in page_info])
            st.dataframe(diagnostic,hide_index=True,use_container_width=True)

        st.subheader("4) Review page choices (change if needed)")
        review=df[["List position","Survey number","Choose original PDF page"]].copy()
        review["Choose original PDF page"]=pd.to_numeric(review["Choose original PDF page"],errors="coerce")
        edited=st.data_editor(review,hide_index=True,use_container_width=True,num_rows="fixed",key="survey_page_review_final",
            column_config={
                "List position":st.column_config.NumberColumn(disabled=True),
                "Survey number":st.column_config.TextColumn(disabled=True),
                "Choose original PDF page":st.column_config.NumberColumn(min_value=1,max_value=len(doc),step=1,help="Select the original PDF page for this survey number. Leave blank to skip.")
            })

        selected=[]
        skipped=[]
        for i,(raw,key) in enumerate(master):
            value=edited.iloc[i]["Choose original PDF page"]
            pno=None if pd.isna(value) else int(value)
            if pno and 1<=pno<=len(doc):
                selected.append({"list_pos":i+1,"survey":raw,"key":key,"source_page":pno})
            else:
                skipped.append((i+1,raw))

        st.subheader("5) Download segregated PDF")
        if selected:
            output_data=make_output_pdf(doc,selected)
            st.success(f"Ready to download: {len(selected)} page(s). Pages are in your requested sequence; other pages are excluded.")
            st.download_button("⬇️ DOWNLOAD FINAL SEQUENCED PDF",data=output_data,
                file_name="survey_pages_sequenced.pdf",mime="application/pdf",type="primary",use_container_width=True)
        else:
            st.warning("No pages are selected/matched. Fill in the original PDF page numbers in Step 4; once at least one page is selected, the final PDF download button will appear.")

        if skipped:
            st.warning(f"{len(skipped)} requested item(s) will be skipped.")
            with st.expander("Skipped survey numbers"):
                st.dataframe(pd.DataFrame(skipped,columns=["List position","Survey number"]),hide_index=True)

        report=df.copy()
        report["Final source page"]=[None if pd.isna(x) else int(x) for x in edited["Choose original PDF page"]]
        st.download_button("Download optional matching report (CSV)",report.to_csv(index=False).encode("utf-8-sig"),"survey_page_matching_report.csv","text/csv")
        doc.close()
    except Exception as error:
        st.error(f"Unable to process PDF: {error}")
elif uploaded and not master:
    st.info("Paste the sequence list to begin.")
else:
    st.info("Upload the PDF and paste the survey-number list.")

st.divider()
st.caption("Auto matching reads searchable PDF text around survey-field labels. Image-only scanned PDFs need OCR; this code does not include Gujarati OCR.")
