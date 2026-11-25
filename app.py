import io, re, unicodedata, difflib
import fitz
import pandas as pd
import streamlit as st

st.set_page_config(page_title='Gujarati PDF Survey Sequencer', layout='wide')
st.title('Gujarati Survey Number PDF Sequencer')
st.write('Reads ONLY the Gujarati field “બ્લોક/સરવે નંબર :” (and close OCR variants), then exports matching pages in your list order. Extra pages are excluded.')

GUJ = str.maketrans('૦૧૨૩૪૫૬૭૮૯', '0123456789')

def norm(s):
    s = (s or '').translate(GUJ)
    s = unicodedata.normalize('NFKC', s)
    return re.sub(r'\s+', ' ', s).strip()

def canonical(s):
    s = norm(s).lower().replace('પૈકી', '/').replace('paiki', '/').replace('\\', '/')
    s = re.sub(r'\s*/\s*', '/', s)
    s = re.sub(r'[^0-9/.-]', '', s)
    s = re.sub(r'/+', '/', s).strip('/')
    return s

def parse_master(raw):
    result=[]
    for x in re.split(r'[\n,;]+', norm(raw)):
        x=x.strip()
        if x:
            x=re.sub(r'\s*(?:પૈકી|paiki)\s*', '/', x, flags=re.I).replace('\\','/').replace(' ','')
            result.append(canonical(x))
    return result

# Target label: બ્લોક/સરવે નંબર. OCR may split words or confuse સરવે/સર્વે.
LABEL_PATTERNS = [
    r'બ્લોક\s*/?\s*સરવે\s*નં?બર?', r'બ્લોક\s*/?\s*સર્વે\s*નં?બર?',
    r'બ્લોક\s*નં?બર?\s*[/ -]?\s*સરવે', r'સરવે\s*નં?બર?', r'સર્વે\s*નં?બર?',
    r'block\s*/?\s*survey\s*(?:no\.?|number)?', r'block\s*/?\s*servey\s*(?:no\.?|number)?'
]
LABEL_RE = re.compile('|'.join('(?:'+p+')' for p in LABEL_PATTERNS), re.I)
NUM_RE = re.compile(r'(?<![\w])([0-9]{1,6}(?:\s*[./-]\s*[0-9]{1,4})?)(?![\w])')

def extract_after_label(text):
    t=norm(text)
    # Search across newlines and OCR-normalized text; only capture number after target label.
    for lm in LABEL_RE.finditer(t):
        tail=t[lm.end():lm.end()+160]
        tail=re.sub(r'^[\s:：#№\-]+','',tail)
        m=NUM_RE.search(tail)
        if m:
            v=canonical(m.group(1))
            if v: return v
    # Gujarati OCR may split the field label into separate words; fuzzy line check,
    # then inspect only that line and the next line for its value.
    lines=[norm(x) for x in (text or '').splitlines() if norm(x)]
    target='બ્લોક સરવે નંબર'
    for i,line in enumerate(lines):
        compact=re.sub(r'\s+','',line)
        score=max(difflib.SequenceMatcher(None, compact, re.sub(r'\s+','',target)).ratio(),
                 difflib.SequenceMatcher(None, compact, re.sub(r'\s+','', 'બ્લોક સર્વે નંબર')).ratio())
        if score >= .48 or ('બ્લોક' in line and ('સરવે' in line or 'સર્વે' in line)):
            after=line + (' '+lines[i+1] if i+1<len(lines) else '')
            nums=NUM_RE.findall(after)
            if nums:
                # Prefer a number after colon; otherwise first number on matched label line/next line.
                v=canonical(nums[0]);
                if v:return v
    return None

def ocr_image(img, pytesseract):
    # Multiple layouts improve recognition of forms with label/value on a separate line.
    outputs=[]
    for psm in (6, 11, 4, 12):
        try:
            outputs.append(pytesseract.image_to_string(img, lang='guj+eng', config=f'--psm {psm}'))
        except Exception:
            pass
    return '\n'.join(outputs)

def detect_page(page, pytesseract, Image):
    txt=page.get_text('text') or ''
    val=extract_after_label(txt)
    if val: return val, 'Embedded PDF text', txt, ''
    pix=page.get_pixmap(matrix=fitz.Matrix(3,3), alpha=False)
    image=Image.open(io.BytesIO(pix.tobytes('png')))
    ocrtxt=ocr_image(image, pytesseract)
    val=extract_after_label(ocrtxt)
    if val: return val, 'Gujarati+English OCR (whole page, multiple layouts)', txt, ocrtxt
    # Try OCR on 3 vertical bands as the field often sits in the upper half of land-record forms.
    w,h=image.size
    crops=[image.crop((0,0,w,int(h*.60))), image.crop((0,int(h*.15),w,int(h*.85))), image.crop((0,int(h*.35),w,h))]
    for ci,crop in enumerate(crops,1):
        ctext=ocr_image(crop, pytesseract)
        val=extract_after_label(ctext)
        if val: return val, f'Gujarati+English OCR (region {ci})', txt, ocrtxt+'\n[REGION OCR]\n'+ctext
    return None, 'OCR attempted; target label/value not found', txt, ocrtxt

pdf=st.file_uploader('Upload original Gujarati land-record PDF', type=['pdf'])
sequence=st.text_area('Paste survey-number sequence (one number per line; your order is preserved)', height=220,
                     placeholder='૧૬૨\n૧૬૪\n૧૬૫\n૧૬૯\n૧૭૪\n...')
use_ocr=st.checkbox('Gujarati OCR fallback enabled', value=True)

if pdf and sequence.strip():
    requested=parse_master(sequence)
    try: doc=fitz.open(stream=pdf.getvalue(), filetype='pdf')
    except Exception as e: st.error(f'Cannot open PDF: {e}'); st.stop()
    try:
        import pytesseract
        from PIL import Image
        ocr_ready=True
        try:
            langs=pytesseract.get_languages(config='')
            if 'guj' not in langs or 'eng' not in langs: ocr_ready=False
        except Exception: ocr_ready=False
    except Exception:
        pytesseract=None; Image=None; ocr_ready=False
    detected=[]; diagnostics=[]
    progress=st.progress(0, text='Scanning target survey field on every page…')
    for i,page in enumerate(doc):
        value=None; method='Embedded text only'; rawtext=page.get_text('text') or ''; ocrtext=''
        value=extract_after_label(rawtext)
        if value: method='Embedded PDF text: target label matched'
        elif use_ocr and ocr_ready:
            value,method,rawtext,ocrtext=detect_page(page,pytesseract,Image)
        elif use_ocr and not ocr_ready:
            method='OCR unavailable: Tesseract Gujarati (guj) + English (eng) required'
        detected.append(value)
        diagnostics.append({'PDF page':i+1,'Survey field value detected':value or 'Not found','Detection method':method,
                           'PDF text preview':norm(rawtext)[:220], 'OCR preview':norm(ocrtext)[:300]})
        progress.progress((i+1)/max(1,len(doc)), text=f'Checking page {i+1}/{len(doc)}')
    progress.empty()
    # Match by survey-number field only. Preserve list order; page reuse is prevented.
    matches=[]; missing=[]; used=set()
    for s in requested:
        ix=next((j for j,v in enumerate(detected) if j not in used and canonical(v or '')==canonical(s)),None)
        if ix is None: missing.append(s)
        else: used.add(ix); matches.append((s,ix))
    st.subheader('Survey field scan results')
    st.write(f'Requested: **{len(requested)}** | Matched: **{len(matches)}** | Missing: **{len(missing)}**')
    if missing: st.warning('Not detected in target field: '+', '.join(missing))
    with st.expander('Detection details for each PDF page', expanded=(len(matches)==0)):
        st.dataframe(pd.DataFrame(diagnostics), use_container_width=True, hide_index=True)
    if matches:
        out=fitz.open()
        for survey,ix in matches: out.insert_pdf(doc,from_page=ix,to_page=ix)
        data=out.tobytes(garbage=4,deflate=True); out.close()
        st.success(f'Output PDF created with {len(matches)} selected pages, in the exact pasted order. All other pages removed.')
        st.download_button('⬇️ DOWNLOAD SEQUENCED PDF',data=data,file_name='Gujarati_survey_pages_sequenced.pdf',mime='application/pdf',type='primary',use_container_width=True)
        st.download_button('Optional matching CSV report',data=pd.DataFrame([{'Survey':s,'Original PDF page':ix+1} for s,ix in matches]).to_csv(index=False).encode('utf-8-sig'),file_name='matched_pages.csv',mime='text/csv')
    else:
        st.error('No survey-number pages detected. OCR was attempted if enabled. Check detection details below; if OCR is not installed on deployment, install the packages listed in the ZIP.')
        st.download_button('Optional scan report CSV',data=pd.DataFrame(diagnostics).to_csv(index=False).encode('utf-8-sig'),file_name='survey_detection_diagnostics.csv',mime='text/csv')
else:
    st.info('Upload the PDF and paste the list to scan the target Gujarati survey field.')
