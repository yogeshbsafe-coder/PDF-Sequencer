import re, io
from collections import defaultdict, Counter
import fitz
import pandas as pd
import streamlit as st

st.set_page_config(page_title="PDF Survey Sequencer", page_icon="📄", layout="wide")
st.title("PDF Survey Number Sequencer")
st.write("Upload a PDF, paste the required survey-number order, and download a new PDF containing only matching pages.")

GUJ=str.maketrans("૦૧૨૩૪૫૬૭૮૯","0123456789")
def norm(s):
    s=str(s).translate(GUJ).strip().replace("પૈકી","/p")
    s=re.sub(r"\s+","",s)
    s=re.sub(r"/+","/",s)
    return s.strip(",;")
def split_seq(s):
    return [norm(x) for x in re.split(r"[\n,;]+",s) if norm(x)]
def tokens(s):
    s=s.translate(GUJ).replace("પૈકી","/p")
    return [norm(x) for x in re.findall(r"(?<![A-Za-z0-9])\d{1,6}(?:\s*(?:/|\.|-)\s*(?:p\s*)?\d{1,4})?(?![A-Za-z0-9])",s,re.I)]
pdf=st.file_uploader("Upload source PDF",type=["pdf"])
seq=st.text_area("Paste survey numbers in required order",height=220,placeholder="162\n164\n165\n169")
st.caption("Gujarati and English digits supported. Scanned PDFs need OCR/searchable text for reliable matching.")
if pdf and seq.strip():
    doc=fitz.open(stream=pdf.getvalue(),filetype="pdf")
    pmap=defaultdict(list); allnums=[]
    for i,p in enumerate(doc):
        nums=list(dict.fromkeys(tokens(p.get_text("text"))))
        for n in nums:
            pmap[n].append(i); allnums.append(n)
    wanted=split_seq(seq); selected=[]; matched=[]; missing=[]
    for n in wanted:
        pages=pmap.get(n,[])
        if pages:
            matched.append({"Survey number":n,"PDF page(s)":", ".join(str(x+1) for x in pages)})
            selected.extend(pages)
        else: missing.append(n)
    selected=list(dict.fromkeys(selected))
    dups=sorted(n for n,c in Counter(allnums).items() if c>1)
    not_list=sorted(set(pmap)-set(wanted))
    a,b,c=st.columns(3); a.metric("Source pages",len(doc)); b.metric("Requested numbers",len(wanted)); c.metric("Selected pages",len(selected))
    st.subheader("Matching preview")
    if matched: st.dataframe(pd.DataFrame(matched),use_container_width=True,hide_index=True)
    else: st.warning("No exact matches found. Confirm PDF text or survey-number formatting.")
    x,y=st.columns(2)
    with x:
        st.markdown("**Not found in PDF**"); st.write(", ".join(missing) or "None")
        st.markdown("**Repeated numbers detected in PDF**"); st.write(", ".join(dups) or "None")
    with y:
        st.markdown("**In PDF but not in your list**"); st.write(", ".join(not_list) or "None")
        st.markdown("**Pages skipped**"); st.write(len(doc)-len(selected))
    if selected:
        out=fitz.open()
        for i in selected: out.insert_pdf(doc,from_page=i,to_page=i)
        st.download_button("Download sequenced PDF",out.tobytes(),"Sequenced_Survey_Pages.pdf","application/pdf",type="primary")
    report=["PDF SURVEY SEQUENCING REPORT",f"Source pages: {len(doc)}",f"Requested numbers: {len(wanted)}",f"Selected pages: {len(selected)}","","MATCHED:"]
    report += [f"{r['Survey number']}: PDF page(s) {r['PDF page(s)']}" for r in matched]
    report += ["","NOT FOUND:",", ".join(missing) or "None","", "REPEATED IN PDF:",", ".join(dups) or "None","", "IN PDF BUT NOT IN LIST:",", ".join(not_list) or "None"]
    st.download_button("Download report", "\n".join(report).encode("utf-8"),"Sequencing_Report.txt","text/plain")
elif pdf: st.info("Paste the required sequence to continue.")
