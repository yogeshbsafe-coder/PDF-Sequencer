import re, io, unicodedata
import fitz
import pandas as pd
import streamlit as st

st.set_page_config(page_title='PDF Survey Sequencer', layout='wide')
st.title('PDF Survey Sequencer — Automatic Survey Page Extraction')
st.write('Upload a PDF and your survey-number sequence. The app reads the survey field (text extraction first, Gujarati/English OCR fallback), keeps only matching pages, and exports them in your exact requested order.')

GUJ = str.maketrans('૦૧૨૩૪૫૬૭૮૯', '0123456789')

def norm(s):
    s = (s or '').translate(GUJ)
    s = unicodedata.normalize('NFKC', s)
    return re.sub(r'\s+', ' ', s).strip()

def canonical(s):
    s = norm(s).lower().replace('પૈકી','/').replace('paiki','/').replace('\\','/')
    s = re.sub(r'\s*/\s*', '/', s)
    s = re.sub(r'[^0-9/.-]', '', s)
    s = re.sub(r'/+', '/', s).strip('/')
    return s

def parse_master(raw):
    out=[]
    for part in re.split(r'[\n,;]+', norm(raw)):
        p=part.strip()
        if not p: continue
        p=re.sub(r'\s*(?:પૈકી|paiki)\s*', '/', p, flags=re.I)
        p=p.replace('\\','/').replace(' ', '')
        out.append(p)
    return out

# Survey labels commonly printed on Gujarat land-record forms, including OCR-friendly variants.
LABELS = [r'બ્લોક\s*/?\s*સરવે', r'બ્લોક\s*/?\s*સર્વે', r'સરવે', r'સર્વે',
          r'બ્લોક\s*/?\s*સર્વે\s*નં?', r'બ્લોક\s*નં?', r'survey', r'block\s*/?\s*survey', r'block']
LABEL_RE = re.compile('|'.join('(?:'+x+')' for x in LABELS), re.I)
NUM_RE = re.compile(r'([0-9]{1,6}(?:\s*[./-]\s*[0-9]{1,4})?)')

def candidates_from_text(text):
    text=norm(text)
    if not text: return []
    found=[]
    # Label/value same-line and label/value on adjacent OCR/text lines.
    lines=[norm(x) for x in text.splitlines() if norm(x)]
    for i,line in enumerate(lines):
        if LABEL_RE.search(line):
            neighborhood=line
            if i+1 < len(lines): neighborhood += ' ' + lines[i+1]
            if i+2 < len(lines) and len(line)<35: neighborhood += ' ' + lines[i+2]
            # inspect after each recognized label; values may be separated by colon or whitespace
            for lab in LABEL_RE.finditer(neighborhood):
                tail=neighborhood[lab.end():lab.end()+120]
                tail=re.sub(r'^[\s:：#№\-]+','',tail)
                m=NUM_RE.match(tail)
                if m:
                    value=canonical(m.group(1))
                    if value: found.append(value)
    # fallback: OCR/text often collapses label and value; use the first number shortly after label
    for m in LABEL_RE.finditer(text):
        tail=text[m.end():m.end()+100]
        nm=NUM_RE.search(tail)
        if nm:
            value=canonical(nm.group(1))
            if value: found.append(value)
    return list(dict.fromkeys(x for x in found if x))

def ocr_page(page):
    """Gujarati + English OCR; gracefully return a diagnostic if Tesseract is absent."""
    try:
        import pytesseract
        pix=page.get_pixmap(matrix=fitz.Matrix(2.5,2.5), alpha=False)
        img=Image.open(io.BytesIO(pix.tobytes('png')))
        return pytesseract.image_to_string(img, lang='guj+eng', config='--psm 6')
    except Exception as e:
        return ''

# Pillow import for OCR image conversion
try:
    from PIL import Image
except Exception:
    Image=None

pdf_file=st.file_uploader('Upload original PDF', type=['pdf'])
sequence=st.text_area('Survey-number sequence (one per line; duplicates/order preserved)', height=220, placeholder='162\n164\n165\n169\n174\n175\n293\n...')
use_ocr=st.checkbox('Enable Gujarati/English OCR fallback for image/scanned pages', value=True)

if pdf_file and sequence.strip():
    try: doc=fitz.open(stream=pdf_file.getvalue(), filetype='pdf')
    except Exception as e:
        st.error(f'PDF could not be opened: {e}'); st.stop()
    requested=parse_master(sequence)
    page_ids=[]; diag=[]
    progress=st.progress(0, text='Reading PDF pages…')
    for page_index,page in enumerate(doc):
        extracted=page.get_text('text') or ''
        found=candidates_from_text(extracted)
        source='PDF text'
        ocr_text=''
        if not found and use_ocr and Image is not None:
            ocr_text=ocr_page(page)
            found=candidates_from_text(ocr_text)
            source='Gujarati/English OCR' if found else ('OCR attempted' if ocr_text else 'OCR unavailable')
        page_ids.append(found)
        diag.append({'Original PDF page':page_index+1,'Detected survey field value(s)':', '.join(found) or 'Not detected','Read method':source,
                    'Extracted text preview':(norm(ocr_text or extracted)[:180] if (ocr_text or extracted) else '(no text)' )})
        progress.progress((page_index+1)/len(doc), text=f'Reading page {page_index+1} of {len(doc)}…')
    progress.empty()
    matched=[]; missing=[]; used=set()
    for survey in requested:
        key=canonical(survey)
        match=next((idx for idx,vals in enumerate(page_ids) if idx not in used and key in vals),None)
        if match is not None:
            used.add(match); matched.append((survey,match))
        else: missing.append(survey)
    st.subheader('Automatic matching')
    st.write(f'List items: **{len(requested)}** | matched: **{len(matched)}** | not found: **{len(missing)}**')
    if missing: st.warning('Not found: ' + ', '.join(missing))
    with st.expander('Page detection details (for troubleshooting)', expanded=(len(matched)==0)):
        st.dataframe(pd.DataFrame(diag), use_container_width=True, hide_index=True)
    if matched:
        out=fitz.open()
        for _,page_idx in matched: out.insert_pdf(doc, from_page=page_idx, to_page=page_idx)
        pdf_bytes=out.tobytes(garbage=4, deflate=True); out.close()
        st.success(f'Final PDF ready: {len(matched)} pages, arranged in the requested list order. All other pages excluded.')
        st.download_button('⬇️ DOWNLOAD SEQUENCED PDF', data=pdf_bytes, file_name='survey_pages_in_requested_sequence.pdf', mime='application/pdf', type='primary', use_container_width=True)
        report=pd.DataFrame([{'Requested survey':s,'Original PDF page':p+1} for s,p in matched])
        st.download_button('Optional: Download matching report CSV', data=report.to_csv(index=False).encode('utf-8-sig'), file_name='survey_match_report.csv', mime='text/csv')
    else:
        st.error('No survey-number pages detected. OCR was attempted if enabled. Check detection details below; if OCR is not installed on deployment, install the packages listed in the ZIP.')
        st.download_button('Download detection report CSV (optional)', data=pd.DataFrame(diag).to_csv(index=False).encode('utf-8-sig'), file_name='survey_detection_diagnostics.csv', mime='text/csv')
else:
    st.info('Upload a PDF and enter your survey-number sequence to begin.')
