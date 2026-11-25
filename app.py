import re
import io
import unicodedata
import fitz
import pandas as pd
import streamlit as st

st.set_page_config(page_title='PDF Survey Sequencer', layout='wide')
st.title('PDF Survey Sequencer — Automatic PDF Output')
st.write('Upload the original PDF and paste survey numbers in the required order. The app finds pages automatically and creates a new PDF containing only matching pages.')

GUJ = str.maketrans('૦૧૨૩૪૫૬૭૮૯', '0123456789')

def norm(s):
    s = (s or '').translate(GUJ)
    s = unicodedata.normalize('NFKC', s)
    return re.sub(r'\s+', ' ', s).strip()

def parse_master(raw):
    # one item per line; also accepts comma/semicolon-separated entries
    raw = raw.translate(GUJ)
    out=[]
    for part in re.split(r'[\n,;]+', raw):
        p=part.strip()
        if not p: continue
        # Convert typical Gujarati paiki notation into normalized suffix notation
        p=re.sub(r'\s*(?:પૈકી|paiki)\s*', '/', p, flags=re.I)
        p=p.replace('\\','/').replace(' ', '')
        out.append(p)
    return out

def canonical(s):
    s=norm(s).lower().replace('પૈકી','/').replace('paiki','/')
    s=s.replace('\\','/')
    s=re.sub(r'[^0-9/.-]', '', s)
    s=re.sub(r'/+', '/', s).strip('/')
    return s

LABELS = [r'બ્લોક\s*/?\s*સરવે\s*(?:નંબર|નં\.?|no\.?|number)?',
          r'સરવે\s*(?:નંબર|નં\.?|no\.?|number)', r'સર્વે\s*(?:નંબર|નં\.?|no\.?|number)',
          r'બ્લોક\s*(?:નંબર|નં\.?|no\.?|number)', r'survey\s*(?:no\.?|number)', r'block\s*/?\s*survey\s*(?:no\.?|number)']
LABEL_RE = re.compile('|'.join('(?:'+x+')' for x in LABELS), re.I)

def page_survey_candidates(text):
    text=norm(text)
    found=[]
    # Read text immediately after survey label, within the same line or nearby line.
    for m in LABEL_RE.finditer(text):
        tail=text[m.end():m.end()+90]
        # skip separators, capture number optionally with subpart
        tail=re.sub(r'^[\s:：#№\-]+', '', tail)
        mm=re.match(r'(\d{1,6}(?:[./-]\d{1,4})?)', tail)
        if mm:
            found.append(canonical(mm.group(1)))
    # line-based fallback: if label and value are split across lines
    lines=[norm(x) for x in (text or '').splitlines() if norm(x)]
    for i,line in enumerate(lines):
        if LABEL_RE.search(line):
            joined=line
            if i+1 < len(lines): joined += ' '+lines[i+1]
            for m in LABEL_RE.finditer(joined):
                tail=joined[m.end():m.end()+80]
                tail=re.sub(r'^[\s:：#№\-]+','',tail)
                mm=re.match(r'(\d{1,6}(?:[./-]\d{1,4})?)',tail)
                if mm: found.append(canonical(mm.group(1)))
    return list(dict.fromkeys(x for x in found if x))

uploaded=st.file_uploader('Upload original PDF', type=['pdf'])
master_raw=st.text_area('Paste required survey sequence (one per line; Gujarati or English digits)', height=220, placeholder='162\n164\n165\n169\n...')

if uploaded and master_raw.strip():
    try:
        doc=fitz.open(stream=uploaded.getvalue(), filetype='pdf')
    except Exception as e:
        st.error(f'Could not open PDF: {e}')
        st.stop()
    wanted=parse_master(master_raw)
    page_candidates=[]
    diagnostics=[]
    for pi,page in enumerate(doc):
        text=page.get_text('text')
        candidates=page_survey_candidates(text)
        page_candidates.append(candidates)
        diagnostics.append({'PDF page':pi+1,'Detected survey field':', '.join(candidates) if candidates else 'Not detected'})
    # Keep master-list duplicates. For each requested item, use the next unused page matching exact canonical ID.
    used=set(); matched=[]; missing=[]
    for item in wanted:
        key=canonical(item)
        choices=[i for i,cands in enumerate(page_candidates) if i not in used and key in cands]
        if choices:
            chosen=choices[0]; used.add(chosen); matched.append((item,chosen))
        else:
            missing.append(item)
    st.subheader('Automatic matching results')
    st.write(f'List entries: **{len(wanted)}** · matched pages: **{len(matched)}** · not found: **{len(missing)}**')
    if missing:
        st.warning('Not found: '+', '.join(missing))
    with st.expander('Page detection diagnostics'):
        st.dataframe(pd.DataFrame(diagnostics), use_container_width=True, hide_index=True)
    if matched:
        out=fitz.open()
        for _,idx in matched:
            out.insert_pdf(doc, from_page=idx, to_page=idx)
        pdf_bytes=out.tobytes(garbage=4, deflate=True)
        out.close()
        st.success(f'Final PDF created: {len(matched)} pages in your requested order. Extra pages are excluded.')
        st.download_button('⬇️ Download sequenced PDF', data=pdf_bytes, file_name='survey_numbers_sequenced.pdf', mime='application/pdf', type='primary', use_container_width=True)
        report=pd.DataFrame([{'Requested survey':s,'Original PDF page':p+1} for s,p in matched])
        st.download_button('Download match report (CSV, optional)', data=report.to_csv(index=False).encode('utf-8-sig'), file_name='survey_match_report.csv', mime='text/csv')
    else:
        st.error('No survey pages matched automatically. This is usually because the PDF is scanned/image-only or the survey field text layout differs. No manual page-number Step 4 is used in this version.')
else:
    st.info('Upload a PDF and enter your survey sequence to start.')
