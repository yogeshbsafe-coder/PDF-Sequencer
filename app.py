import re
import hashlib
import pandas as pd
import streamlit as st

try:
    import pymupdf as fitz
except ImportError:
    import fitz

st.set_page_config(page_title="PDF Survey Sequencer", page_icon="📄", layout="wide")
st.title("📄 PDF Survey Sequencer — Exact Master List Order")
st.write("The pasted master list controls the output sequence. The app does not sort survey numbers numerically.")

GUJ_DIGITS = str.maketrans("૦૧૨૩૪૫૬૭૮૯", "0123456789")
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
EN_TO_GUJ = str.maketrans("0123456789", "૦૧૨૩૪૫૬૭૮૯")


def normalize(s):
    s = str(s or "").translate(GUJ_DIGITS).translate(ARABIC_DIGITS).strip()
    s = re.sub(r"\s+", "", s)
    return s


def to_guj(s):
    return str(s).translate(EN_TO_GUJ)


def parse_master(raw):
    # Preserve every item in the user's original order, including duplicates.
    return [normalize(x) for x in re.split(r"[,;\n]+", raw or "") if normalize(x)]


def page_text(page):
    try:
        return page.get_text("text") or ""
    except Exception:
        return ""


def nums_in_text(text):
    text = text.translate(GUJ_DIGITS).translate(ARABIC_DIGITS)
    return [normalize(x) for x in re.findall(r"(?<![\w])\d+(?:[./-]\d+)*(?![\w])", text) if normalize(x)]


def labeled_survey_numbers(text):
    """Only collect numbers from lines containing survey/block label words."""
    found = []
    for line in text.splitlines():
        low = line.lower()
        if any(label in low for label in ("survey", "block", "સર્વે", "સરવે", "બ્લોક")):
            found.extend(nums_in_text(line))
    return list(dict.fromkeys(found))


def render_page(page):
    return page.get_pixmap(matrix=fitz.Matrix(1.15, 1.15), alpha=False).tobytes("png")


pdf_file = st.file_uploader("Upload source PDF", type=["pdf"])
master_text = st.text_area("Paste master survey list (one item per line; order preserved)", height=250,
                           placeholder="૨\n૩\n૫૬\n૩૭૬\n...")
master = parse_master(master_text)
if master:
    st.caption(f"Master list entries: {len(master)} — order and duplicate entries preserved.")

if pdf_file and master and st.button("Analyze PDF", type="primary"):
    try:
        doc = fitz.open(stream=pdf_file.getvalue(), filetype="pdf")
    except Exception as e:
        st.error(f"Could not open PDF: {e}")
        st.stop()
    pages = []
    for i, page in enumerate(doc):
        text = page_text(page)
        label_nums = labeled_survey_numbers(text)
        all_nums = nums_in_text(text)
        pages.append({"page": i + 1, "text": text[:3000], "labeled": label_nums, "all_nums": all_nums})
    doc.close()
    st.session_state.pages = pages
    st.session_state.pdf_bytes = pdf_file.getvalue()
    st.session_state.master = master
    st.session_state.source_name = pdf_file.name
    st.session_state.pop("export_pdf", None)
    st.success("Analysis done. Suggestions are based only on lines containing survey/block labels. Please verify with page previews.")

if "pages" in st.session_state:
    pages = st.session_state.pages
    master = st.session_state.master
    pdf_bytes = st.session_state.pdf_bytes
    page_choices = ["— Not mapped —"] + [f"Page {p['page']}" for p in pages]

    st.subheader("Page mapping — one row per master-list item")
    st.info("A suggestion is made only when the survey number appears on a line containing Survey/Block label text. If Gujarati text extraction is unreadable or no label is detected, the suggestion stays blank. Review every row and preview the source page.")

    rows = []
    for pos, survey in enumerate(master, start=1):
        exact_pages = [p["page"] for p in pages if survey in p["labeled"]]
        anywhere_pages = [p["page"] for p in pages if survey in p["all_nums"]]
        suggest = exact_pages[0] if exact_pages else None
        rows.append({
            "List position": pos,
            "Survey no.": to_guj(survey),
            "Label match pages": ", ".join(map(str, exact_pages)) if exact_pages else "No labeled match",
            "Other text match pages": ", ".join(map(str, anywhere_pages)) if anywhere_pages and not exact_pages else "",
            "Page selection": page_choices[suggest] if suggest else page_choices[0],
        })

    df = pd.DataFrame(rows)
    edited = st.data_editor(
        df,
        hide_index=True,
        num_rows="fixed",
        width="stretch",
        column_config={
            "List position": st.column_config.NumberColumn(disabled=True),
            "Survey no.": st.column_config.TextColumn(disabled=True),
            "Label match pages": st.column_config.TextColumn(disabled=True),
            "Other text match pages": st.column_config.TextColumn(disabled=True),
            "Page selection": st.column_config.SelectboxColumn(options=page_choices, required=True),
        },
        key="mapping_editor_" + hashlib.sha1((st.session_state.source_name + "|" + "|".join(master)).encode()).hexdigest()[:12],
    )

    st.subheader("Source page preview")
    preview = st.selectbox("Choose source PDF page to inspect", [p["page"] for p in pages], key="preview_select")
    preview_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    st.image(render_page(preview_doc[preview - 1]), caption=f"Original source page {preview}")
    st.text_area("Extracted page text", pages[preview - 1]["text"], height=160, disabled=True)
    preview_doc.close()

    ordered_pages, unmapped = [], []
    for _, row in edited.iterrows():
        sel = row["Page selection"]
        if sel == page_choices[0]:
            unmapped.append((int(row["List position"]), row["Survey no."]))
        else:
            ordered_pages.append(int(sel.replace("Page ", "")))

    st.subheader("Export status")
    a, b, c = st.columns(3)
    a.metric("Master list rows", len(master))
    b.metric("Mapped rows", len(ordered_pages))
    c.metric("Unmapped rows", len(unmapped))
    if unmapped:
        st.warning("Unmapped rows will be skipped. Export is available for mapped rows only; the sequence follows the master list order.")
        st.dataframe(pd.DataFrame(unmapped, columns=["List position", "Unmapped survey no."]), hide_index=True)
    else:
        st.success("All master-list rows have a page selected.")

    # Build output automatically on every rerun after mapping; no extra Create button needed.
    export_bytes = b""
    if ordered_pages:
        src = fitz.open(stream=pdf_bytes, filetype="pdf")
        out = fitz.open()
        for page_no in ordered_pages:
            out.insert_pdf(src, from_page=page_no - 1, to_page=page_no - 1)
        export_bytes = out.tobytes(garbage=4, deflate=True)
        out.close()
        src.close()
        st.success(f"Ready to download: {len(ordered_pages)} pages, in pasted master-list order. Skipped {len(unmapped)} unmapped rows.")
    else:
        st.warning("No source pages are mapped yet. Select a page in at least one Page selection row to enable the PDF download.")

    # Put the PDF control first and make its visibility explicit.
    st.markdown("### 📥 Downloads")
    if ordered_pages:
        pdf_col, csv_col = st.columns([2, 1])
        with pdf_col:
            st.download_button(
                label=f"⬇️ DOWNLOAD SEQUENCED PDF ({len(ordered_pages)} pages)",
                data=export_bytes,
                file_name="survey_pages_master_list_order.pdf",
                mime="application/pdf",
                key="download_sequenced_pdf",
                type="primary",
                use_container_width=True,
                help="Downloads mapped source pages in the exact pasted master-list order."
            )
        with csv_col:
            st.download_button(
                label="⬇️ Download mapping CSV",
                data=edited.to_csv(index=False).encode("utf-8-sig"),
                file_name="survey_page_mapping_audit.csv",
                mime="text/csv",
                key="download_mapping_csv",
                use_container_width=True
            )
    else:
        st.error("PDF export is not ready: select a source page for at least one master-list row above. The PDF download button will appear here as soon as one row is mapped.")
        st.download_button(
            label="⬇️ Download mapping CSV",
            data=edited.to_csv(index=False).encode("utf-8-sig"),
            file_name="survey_page_mapping_audit.csv",
            mime="text/csv",
            key="download_mapping_csv_no_pdf",
            use_container_width=True
        )

else:
    st.info("Upload the PDF, paste the master list, and click Analyze PDF. Then review mappings and create the output PDF.")
