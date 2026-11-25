import re
from collections import defaultdict

import pandas as pd
import streamlit as st

try:
    import pymupdf as fitz
except ImportError:
    import fitz

st.set_page_config(page_title="PDF Survey Sequencer", page_icon="📄", layout="wide")
st.title("📄 PDF Survey Sequencer — Master List Order")
st.write("Master list order is the authority. The app will NOT sort your list numerically. Review page matches, then export pages in the exact order you pasted.")

GUJ_DIGITS = str.maketrans("૦૧૨૩૪૫૬૭૮૯", "0123456789")
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
EN_TO_GUJ = str.maketrans("0123456789", "૦૧૨૩૪૫૬૭૮૯")


def normalize(s):
    s = str(s or "").translate(GUJ_DIGITS).translate(ARABIC_DIGITS).strip()
    s = re.sub(r"\s+", "", s)
    # Keep dots/slashes as meaningful survey-number separators.
    return s


def to_guj(s):
    return str(s).translate(EN_TO_GUJ)


def parse_master(raw):
    # Preserve duplicates and the exact pasted order. Do not sort or deduplicate.
    return [normalize(x) for x in re.split(r"[,;\n]+", raw or "") if normalize(x)]


def extract_page_text(page):
    try:
        return page.get_text("text") or ""
    except Exception:
        return ""


def candidate_numbers(text):
    text = text.translate(GUJ_DIGITS).translate(ARABIC_DIGITS)
    # Include dotted/slashed/hyphenated survey-number forms, but these are only suggestions.
    return list(dict.fromkeys(normalize(x) for x in re.findall(r"(?<![\w])\d+(?:[./-]\d+)*(?![\w])", text) if normalize(x)))


def render_page(page):
    return page.get_pixmap(matrix=fitz.Matrix(1.2, 1.2), alpha=False).tobytes("png")

pdf_file = st.file_uploader("Upload source PDF", type=["pdf"])
master_text = st.text_area("Paste survey-number master list (one item per line; exact order will be preserved)", height=250,
                           placeholder="૨\n૩\n૫૬\n૩૭૬\n...\n૨૨૦૬")
master = parse_master(master_text)

if master:
    st.caption(f"Master list entries: {len(master)}. Duplicates are preserved. Numeric sorting is disabled.")

if pdf_file and master and st.button("Analyze PDF and suggest matches", type="primary"):
    try:
        doc = fitz.open(stream=pdf_file.getvalue(), filetype="pdf")
    except Exception as e:
        st.error(f"PDF open error: {e}")
        st.stop()
    page_info = []
    for i, p in enumerate(doc):
        txt = extract_page_text(p)
        nums = candidate_numbers(txt)
        # Suggest only exact master-list matches; still require the user to review.
        found = [n for n in master if n in nums]
        page_info.append({"page": i + 1, "text": txt[:2000], "candidates": nums, "suggested": found})
    st.session_state.page_info = page_info
    st.session_state.pdf_bytes = pdf_file.getvalue()
    st.session_state.master = master
    st.session_state.file_name = pdf_file.name
    st.success("Analysis finished. Suggestions are not treated as verified; review every assignment below.")

if "page_info" in st.session_state:
    pages = st.session_state.page_info
    master = st.session_state.master
    pdf_bytes = st.session_state.pdf_bytes
    st.subheader("Assign source PDF page to each master-list entry")
    st.warning("Important: numbers detected anywhere on a page can be unrelated (owner/record numbers, old survey numbers, etc.). The suggested page is only a guess. Select the correct page using the page preview. The final PDF follows the master-list rows top-to-bottom exactly.")
    page_options = ["— Not mapped —"] + [f"Page {p['page']}" for p in pages]
    # Build initial suggestion mapping by exact candidate match, using first matching page.
    suggestion = {}
    for item in master:
        matching_pages = [p['page'] for p in pages if item in p['candidates']]
        suggestion[item] = matching_pages[0] if matching_pages else None

    mapping_rows = []
    for i, item in enumerate(master):
        opts = page_options
        suggested_page = suggestion.get(item)
        default_idx = (suggested_page if suggested_page else 0)
        mapping_rows.append({"List position": i + 1, "Master survey no.": to_guj(item), "Page selection": page_options[default_idx] if default_idx else page_options[0]})

    df = pd.DataFrame(mapping_rows)
    edited = st.data_editor(df, hide_index=True, num_rows="fixed", width="stretch",
        column_config={
            "List position": st.column_config.NumberColumn(disabled=True),
            "Master survey no.": st.column_config.TextColumn(disabled=True),
            "Page selection": st.column_config.SelectboxColumn(options=page_options, required=True),
        })

    st.subheader("Page preview for checking")
    preview_page = st.selectbox("View source page", [p["page"] for p in pages], format_func=lambda x: f"Page {x}")
    doc_preview = fitz.open(stream=pdf_bytes, filetype="pdf")
    st.image(render_page(doc_preview[preview_page - 1]), caption=f"Source PDF page {preview_page}")
    st.text_area("Extracted text (may be garbled in some Gujarati PDFs)", pages[preview_page - 1]["text"], height=150, disabled=True)
    doc_preview.close()

    final_page_order = []
    missing_entries = []
    for _, row in edited.iterrows():
        choice = row["Page selection"]
        if choice == "— Not mapped —":
            missing_entries.append((int(row["List position"]), row["Master survey no."]))
        else:
            final_page_order.append(int(choice.replace("Page ", "")))

    st.subheader("Sequence check")
    c1, c2, c3 = st.columns(3)
    c1.metric("Master-list rows", len(master))
    c2.metric("Mapped rows", len(final_page_order))
    c3.metric("Unmapped rows", len(missing_entries))
    if missing_entries:
        st.warning("Some entries are unmapped. You can still create a PDF using mapped rows only; unmapped rows will be skipped. Map the remaining entries if you need a complete output.")
        st.dataframe(pd.DataFrame(missing_entries, columns=["List position", "Missing survey no."]), hide_index=True)
    else:
        st.success("All rows mapped. Export will follow the master list from first row to last row exactly.")

    # Export mapped rows even when some are missing; preserve order and allow repeated source pages.
    if st.button("Create PDF from mapped rows (master-list order)", type="primary"):
        src = fitz.open(stream=pdf_bytes, filetype="pdf")
        out = fitz.open()
        for pno in final_page_order:
            out.insert_pdf(src, from_page=pno - 1, to_page=pno - 1)
        result = out.tobytes(garbage=4, deflate=True)
        out.close(); src.close()
        st.session_state.output_pdf = result
        st.session_state.output_page_order = final_page_order
        st.success(f"PDF created with {len(final_page_order)} mapped rows. {len(missing_entries)} unmapped rows were skipped. Order follows the master list; no numeric sorting was applied.")

    if "output_pdf" in st.session_state:
        st.download_button("Download sequenced PDF", st.session_state.output_pdf,
                          file_name="PDF_exact_master_list_sequence.pdf", mime="application/pdf")
        st.download_button("Download mapping audit CSV", edited.to_csv(index=False).encode("utf-8-sig"),
                          file_name="master_list_page_mapping.csv", mime="text/csv")
else:
    st.info("Upload PDF, paste the master list, then analyze. Page matches must be reviewed before export to prevent incorrect sequencing.")
