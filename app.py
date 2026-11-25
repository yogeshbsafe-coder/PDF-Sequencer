import re, io
from collections import defaultdict
import fitz, pandas as pd, streamlit as st
st.set_page_config(page_title='PDF Survey Sequencer V2', page_icon='📑', layout='wide')
st.title('📑 PDF Survey Sequencer — V2')
st.caption('Map survey numbers to pages, review/correct the map, sequence only requested pages, and report missing/extra/repeated numbers.')
GUJ=str.maketrans('૦૧૨૩૪૫૬૭૮૯','0123456789')
def norm(s):
    s=str(s).translate(GUJ).strip().lower().replace('પૈકી','/p')
    s=re.sub(r'\s+','',s).replace('\\','/')
    s=re.sub(r'/+','/',s)
    s=re.sub(r'/p(?=\d)','p',s)
    s=re.sub(r'p/(?=\d)','p',s)
    return s.strip(' ,;')
def seqparse(s): return [norm(v) for v in re.split(r'[\n,;]+',s.translate(GUJ)) if norm(v)]
TOKEN=re.compile(r'(?<![\w])\d{1,6}(?:\s*(?:/|\.|-)\s*(?:p\s*)?\d{1,4})?(?:\s*p\s*\d{1,4})?(?![\w])',re.I)
LABEL=re.compile(r'(survey|sur\.?\s*no|s\.?\s*no|block\s*no|plot\s*no|સર્વે|સર્વે\s*નં|બ્લોક\s*નં|નંબર)',re.I)
def candidates(text):
    text=text.translate(GUJ).replace('પૈકી','/p')
    all_tokens=list(dict.fromkeys(norm(m.group(0)) for m in TOKEN.finditer(text)))
    label_tokens=[]
    for line in text.splitlines():
        if LABEL.search(line): label_tokens.extend(norm(m.group(0)) for m in TOKEN.finditer(line))
    return list(dict.fromkeys(label_tokens)), all_tokens
def ocr(page):
    try:
        import pytesseract
        from PIL import Image
        px=page.get_pixmap(matrix=fitz.Matrix(2,2),alpha=False)
        return pytesseract.image_to_string(Image.open(io.BytesIO(px.tobytes('png'))),lang='eng+guj')
    except Exception as e: return f'[OCR error: {e}]'
def preview(page): return page.get_pixmap(matrix=fitz.Matrix(1.2,1.2),alpha=False).tobytes('png')
def export_pdf(doc,pages):
    out=fitz.open()
    for page_idx in pages: out.insert_pdf(doc,from_page=page_idx,to_page=page_idx)
    return out.tobytes()
pdf=st.file_uploader('Upload PDF',type=['pdf'])
sequence=st.text_area('Paste survey-number sequence (one per line or comma-separated)',height=170,placeholder='162\n164\n165\n169')
ocr_on=st.checkbox('OCR pages with little/no selectable text (Gujarati + English)',value=True)
if pdf and sequence.strip():
    try: doc=fitz.open(stream=pdf.getvalue(),filetype='pdf')
    except Exception as e: st.error(f'Could not open PDF: {e}'); st.stop()
    wanted=seqparse(sequence); infos=[]; prog=st.progress(0); status=st.empty()
    for idx,page in enumerate(doc):
        text=page.get_text('text') or ''; used=False
        if ocr_on and len(text.strip())<25:
            status.info(f'OCR page {idx+1}/{len(doc)}')
            scanned=ocr(page)
            if not scanned.startswith('[OCR error'): text=(text+'\n'+scanned).strip(); used=True
        labeled, allnums=candidates(text); suggestions=labeled if labeled else allnums
        infos.append({'PDF page':idx+1,'Survey number(s) — edit if needed':', '.join(suggestions),'Label detections':', '.join(labeled),'All detected number candidates':', '.join(allnums[:35]),'OCR used':'Yes' if used else 'No','Text preview':text[:900]})
        prog.progress((idx+1)/len(doc))
    status.empty(); prog.empty()
    st.header('Step 2 — Review and correct the page mapping')
    st.warning('Auto-detection is a suggestion. It can confuse survey numbers with dates, areas, amounts, or other numbers. Correct the editable Survey number(s) column. If a page contains multiple survey numbers, separate them with commas.')
    df=pd.DataFrame(infos)
    editable=st.data_editor(df[['PDF page','Survey number(s) — edit if needed','Label detections','All detected number candidates','OCR used']],hide_index=True,use_container_width=True,num_rows='fixed',column_config={'PDF page':st.column_config.NumberColumn(disabled=True),'Label detections':st.column_config.TextColumn(disabled=True),'All detected number candidates':st.column_config.TextColumn(disabled=True),'OCR used':st.column_config.TextColumn(disabled),'Survey number(s) — edit if needed':st.column_config.TextColumn(help='Edit manually; multiple numbers on a page separated by commas.')})
    with st.expander('View original PDF page to verify mapping'):
        page_num=st.selectbox('Select source page',list(range(1,len(doc)+1)))
        st.image(preview(doc[page_num-1]),caption=f'Original source page {page_num}',use_container_width=True)
        st.text_area('Extracted text',infos[page_num-1]['Text preview'],height=150,disabled=True)
    mapping=defaultdict(list)
    for _,row in editable.iterrows():
        p=int(row['PDF page']); val=str(row['Survey number(s) — edit if needed'] or '')
        for item in re.split(r'[,;\n]+',val):
            key=norm(item)
            if key: mapping[key].append(p)
    matched=[]; missing=[]; output_pages=[]
    for number in wanted:
        pages=mapping.get(number,[])
        if pages:
            matched.append((number,pages))
            for p in pages:
                if p not in output_pages: output_pages.append(p)
        else: missing.append(number)
    repeated={n:sorted(set(ps)) for n,ps in mapping.items() if len(set(ps))>1}
    not_requested=sorted(set(mapping)-set(wanted))
    skipped=sorted(set(range(1,len(doc)+1))-set(output_pages))
    st.header('Step 3 — Matching results')
    a,b,c,d=st.columns(4); a.metric('Source pages',len(doc)); b.metric('Pages in output',len(output_pages)); c.metric('Missing list numbers',len(missing)); d.metric('Skipped pages',len(skipped))
    st.subheader('Matched numbers → original PDF pages')
    if matched: st.dataframe(pd.DataFrame([{'Survey number':n,'Original page(s)':', '.join(map(str,ps))} for n,ps in matched]),hide_index=True,use_container_width=True)
    else: st.warning('No matches yet. Edit the page map above, then recheck.')
    left,right=st.columns(2)
    with left:
        st.markdown('**In your list but not mapped in PDF (missing)**'); st.write(', '.join(missing) or 'None')
        st.markdown('**Survey numbers mapped on multiple source pages**'); st.write('; '.join(f'{n}: pages {ps}' for n,ps in repeated.items()) or 'None detected')
    with right:
        st.markdown('**Mapped in PDF but not requested (extra numbers)**'); st.write(', '.join(not_requested) or 'None')
        st.markdown('**Skipped source page numbers**'); st.write(', '.join(map(str,skipped)) or 'None')
    if output_pages:
        st.download_button('⬇ Download reordered PDF (matching pages only)',export_pdf(doc,[p-1 for p in output_pages]),'Survey_Sequence_Output.pdf','application/pdf',type='primary')
    report=['PDF SURVEY SEQUENCER V2 REPORT',f'Input pages: {len(doc)}',f'Requested list entries: {len(wanted)}',f'Output pages: {len(output_pages)}',f'Skipped original pages: {skipped or "None"}','','MATCHES:']
    report += [f'{n}: original page(s) {ps}' for n,ps in matched]
    report += ['', 'MISSING (requested but no page mapped):',', '.join(missing) or 'None','', 'REPEATED SURVEY NUMBERS (mapped on multiple pages):']
    report += [f'{n}: original pages {ps}' for n,ps in repeated.items()] or ['None']
    report += ['', 'IN PDF MAP BUT NOT REQUESTED:',', '.join(not_requested) or 'None']
    st.download_button('⬇ Download detailed report', '\n'.join(report).encode('utf-8'),'Survey_Sequencer_Report.txt','text/plain')
elif pdf: st.info('Paste your required survey-number sequence to start the matching.')
else: st.info('Upload a PDF to begin.')
