import re
import unicodedata
import io
import pandas as pd
import streamlit as st
import pymupdf

st.set_page_config(page_title="PDF Survey Sequencer", layout="wide")
st.title("PDF Survey Sequencer")
st.write("Upload the original PDF and paste your survey-number list. The app finds matching survey pages, keeps your list order, and creates a new PDF containing only those pages.")

GUJ_DIGITS = "૦૧૨૩૪૫૬૭૮૯"
ENG_DIGITS = "0123456789"
DIGIT_TRANSLATION = str.maketrans(GUJ_DIGITS, ENG_DIGITS)

def digits_to_english(s):
    return str(s).translate(DIGIT_TRANSLATION)

def canonical_survey(value):
    """Normalize Gujarati/English survey number spellings to one comparison key."""
    s = digits_to_english(value or "")
    s = unicodedata.normalize("NFKC", s).lower()
    # Convert common paiki wording to a distinct p marker, not a slash.
    s = re.sub(r"પૈકી|પૈકીનું|paiki|p\.?a\.?i\.?k\.?i\.?", "p", s, flags=re.I)
    s = re.sub(r"\bpart\s*[-:]?\s*", "p", s, flags=re.I)
    s = s.replace("પ", "p")
    # Remove spaces around separators and punctuation, but preserve slash and p.
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[^0-9p/.-]", "", s)
    s = s.replace(".", "/")
    s = re.sub(r"-", "/", s)
    s = re.sub(r"/+", "/", s)
    # Normalize forms like 68/1p 2 -> 68/1p2
    return s.strip("/")

def parse_master_list(raw):
    items=[]
    for line in raw.splitlines():
        for item in re.split(r"[,;]", line):
            item=item.strip()
            if item:
                key=canonical_survey(item)
                if key:
                    items.append((item, key))
    return items

LABEL_PATTERNS = [
    r"બ્લોક\s*/?\s*સરવે", r"બ્લોક", r"સરવે\s*નંબર", r"સર્વે\s*નંબર",
    r"survey\s*(?:no\.?|number)", r"block\s*(?:/|and)?\s*survey", r"block\s*(?:no\.?|number)",
    # Some PDFs have imperfect Gujarati text extraction; retain broad label clues.
    r"લોક\s*/", r"ƞલોક\s*/", r"survey"
]

def get_survey_field(page_text):
    lines=[line.strip() for line in (page_text or "").splitlines() if line.strip()]
    label_re=re.compile("|".join(LABEL_PATTERNS), re.I)
    for idx,line in enumerate(lines):
        if label_re.search(line):
            # value written after a colon on label line
            if ":" in line or "：" in line:
                parts=re.split(r"[:：]", line, maxsplit=1)
                if len(parts)>1 and parts[1].strip():
                    return parts[1].strip()
            # Otherwise the form commonly places the value on following line(s).
            for next_line in lines[idx+1:idx+4]:
                if next_line.strip():
                    return next_line.strip()
    return ""

def extract_key_from_field(field):
    if not field:
        return ""
    # field may have surrounding punctuation or a label fragment
    return canonical_survey(field)

def page_survey_key(text):
    field=get_survey_field(text)
    if field:
        return extract_key_from_field(field), field, "survey field"
    return "", "", "survey field label not detected"

def build_page_index(doc):
    records=[]
    for i,page in enumerate(doc):
        text=page.get_text("text") or ""
        key, field, note=page_survey_key(text)
        records.append({
            "PDF page": i+1,
            "Detected field text": field,
            "Detected survey key": key,
            "Detection": note,
            "Text characters": len(text)
        })
    return pd.DataFrame(records)

def create_output_pdf(doc, ordered_pages):
    out=pymupdf.open()
    toc=[]
    for output_page, (master_row, raw_survey, key, source_page) in enumerate(ordered_pages, start=1):
        out.insert_pdf(doc, from_page=source_page-1, to_page=source_page-1)
        toc.append([1, f"{raw_survey} (source page {source_page})", output_page])
    if toc:
        out.set_toc(toc)
    data=out.tobytes(garbage=4, deflate=True)
    out.close()
    return data

pdf_upload=st.file_uploader("Step 1 — Upload original PDF", type=["pdf"])
master_text=st.text_area(
    "Step 2 — Paste survey numbers in your required sequence (one per line; comma-separated is also accepted)",
    height=230,
    placeholder="25\n27\n30\n31\n44\n52\n60"
)
master=parse_master_list(master_text)

if pdf_upload and master:
    try:
        original_bytes=pdf_upload.getvalue()
        pdf=pymupdf.open(stream=original_bytes, filetype="pdf")
        st.info(f"PDF pages: {len(pdf)} | List entries: {len(master)} (duplicates/order preserved)")
        with st.spinner("Reading survey-number field from each PDF page..."):
            page_index=build_page_index(pdf)

        # Map normalized survey field key -> source page(s); use first page by default,
        # matching the user's prior sequencing workflow. Duplicate master rows remain duplicates.
        key_to_pages={}
        for _, row in page_index.iterrows():
            k=row["Detected survey key"]
            if k:
                key_to_pages.setdefault(k, []).append(int(row["PDF page"]))

        matches=[]
        for row_number,(raw,key) in enumerate(master, start=1):
            pages=key_to_pages.get(key,[])
            matches.append({
                "List row": row_number,
                "Survey number (as pasted)": raw,
                "Normalized key": key,
                "Matching source PDF page(s)": ", ".join(map(str,pages)) if pages else "NOT FOUND",
                "Default source page": pages[0] if pages else None,
                "Status": "Found" if pages else "Not found"
            })
        match_df=pd.DataFrame(matches)
        found_rows=int((match_df["Status"]=="Found").sum())
        st.subheader("Step 3 — Matching report")
        st.write(f"**Matched list entries:** {found_rows} / {len(master)}")
        st.dataframe(match_df, hide_index=True, use_container_width=True)

        with st.expander("See detected survey field from every PDF page"):
            st.dataframe(page_index, hide_index=True, use_container_width=True)

        st.caption("The app uses the first matching source page for each list item by default. Repeated survey numbers in your list are repeated in the output. If more than one source page has the same survey key, choose the correct page below.")
        st.subheader("Step 4 — Review page choices (only if needed)")
        options=[None]+list(range(1,len(pdf)+1))
        review=match_df[["List row","Survey number (as pasted)","Default source page"]].copy()
        review["Default source page"]=pd.to_numeric(review["Default source page"], errors="coerce")
        edited=st.data_editor(
            review,
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            key="page_review_v2",
            column_config={
                "List row":st.column_config.NumberColumn(disabled=True),
                "Survey number (as pasted)":st.column_config.TextColumn(disabled=True),
                "Default source page":st.column_config.NumberColumn(
                    min_value=1,max_value=len(pdf),step=1,
                    help="Keep detected page or enter the correct source page. Leave blank to skip this survey number."
                )
            }
        )

        final_rows=[]
        skipped=[]
        for idx,(raw,key) in enumerate(master):
            value=edited.iloc[idx]["Default source page"]
            page_num=None if pd.isna(value) else int(value)
            if page_num is not None and 1<=page_num<=len(pdf):
                final_rows.append((idx+1,raw,key,page_num))
            else:
                skipped.append((idx+1,raw))
        st.subheader("Step 5 — Download the final sequenced PDF")
        if final_rows:
            final_pdf=create_output_pdf(pdf,final_rows)
            st.download_button(
                "⬇️ Download FINAL Sequenced PDF",
                data=final_pdf,
                file_name="survey_pages_in_master_sequence.pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True
            )
            st.success(f"Final PDF ready: {len(final_rows)} pages. Only selected/matched pages are included, in your list order.")
        else:
            st.warning("No matching pages selected yet. The PDF download button is shown below but disabled until at least one page is matched or selected.")
            st.download_button(
                "⬇️ Download FINAL Sequenced PDF (waiting for matches)",
                data=b"",
                file_name="survey_pages_in_master_sequence.pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True,
                disabled=True
            )

        if skipped:
            st.warning(f"{len(skipped)} list item(s) will be skipped (not found or no page selected).")
            with st.expander("Skipped survey numbers"):
                st.dataframe(pd.DataFrame(skipped,columns=["List row","Survey number"]),hide_index=True)

        # CSV is optional audit only; the main deliverable is the PDF.
        report=match_df.copy()
        report["Final source page"]=[None if pd.isna(x) else int(x) for x in edited["Default source page"]]
        st.download_button("Download matching report (optional CSV)", report.to_csv(index=False).encode("utf-8-sig"),
                          "survey_matching_report.csv", "text/csv")
        pdf.close()
    except Exception as e:
        st.error(f"Could not process this PDF: {e}")
elif pdf_upload and not master:
    st.info("Paste your survey-number list to start matching.")
    st.download_button(
        "⬇️ Download FINAL Sequenced PDF (paste list first)",
        data=b"",
        file_name="survey_pages_in_master_sequence.pdf",
        mime="application/pdf",
        type="primary",
        use_container_width=True,
        disabled=True
    )
else:
    st.info("Upload a PDF and paste the list in your required sequence.")

st.divider()
st.caption("Note: Automatic detection requires text-readable PDF pages. Image-only/scanned pages need OCR; this build does not silently guess survey numbers from unrelated numbers on a page.")
