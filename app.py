import io
import re
import streamlit as st
import pandas as pd
import pymupdf

st.set_page_config(page_title="PDF Survey Sequencer", layout="wide")
st.title("PDF Survey Sequencer — Master List Order")
st.caption("Arrange source PDF pages exactly in the order of your master survey list. Page matches are manually verified.")

def normalize_digits(s):
    guj = "૦૧૨૩૪૫૬૭૮૯"
    eng = "0123456789"
    return s.translate(str.maketrans(guj, eng))

def parse_master(raw):
    # Preserve the exact row order and duplicates; ignore blank lines only.
    return [normalize_digits(line.strip()) for line in raw.splitlines() if line.strip()]

pdf_file = st.file_uploader("Step 1 — Upload original PDF", type=["pdf"])
master_raw = st.text_area("Step 2 — Paste master survey list (one entry per line)", height=220,
                          placeholder="2\n3\n56\n376\n...")
master = parse_master(master_raw)

if pdf_file and master:
    try:
        pdf_bytes = pdf_file.getvalue()
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        st.success(f"Loaded PDF: {len(doc)} pages | Master list: {len(master)} entries")
        st.info("Select the source PDF page for each master-list entry. Entries can use the same source page when needed. Order in the master list is kept exactly.")

        options = ["Not mapped"] + [f"Page {i}" for i in range(1, len(doc)+1)]
        # Build an editable mapping table; selected page values are retained in session state.
        if "mapping_values" not in st.session_state or st.session_state.get("mapping_key") != (pdf_file.name, tuple(master)):
            st.session_state.mapping_values = ["Not mapped"] * len(master)
            st.session_state.mapping_key = (pdf_file.name, tuple(master))

        rows = []
        for idx, survey in enumerate(master):
            rows.append({"Master row": idx+1, "Survey number": survey,
                         "Source PDF page": st.session_state.mapping_values[idx]})
        df = pd.DataFrame(rows)
        edited = st.data_editor(
            df,
            key="mapping_editor",
            hide_index=True,
            width='stretch',
            column_config={
                "Master row": st.column_config.NumberColumn(disabled=True),
                "Survey number": st.column_config.TextColumn(disabled=True),
                "Source PDF page": st.column_config.SelectboxColumn(options=options, required=True)
            },
            disabled=["Master row", "Survey number"],
            num_rows="fixed"
        )
        st.session_state.mapping_values = edited["Source PDF page"].tolist()

        mapped = [(idx, survey, value) for idx, (survey, value) in enumerate(zip(master, st.session_state.mapping_values))
                  if value != "Not mapped"]
        unmapped = [(idx+1, survey) for idx, (survey, value) in enumerate(zip(master, st.session_state.mapping_values))
                    if value == "Not mapped"]
        st.write(f"**Mapped:** {len(mapped)} / {len(master)} entries")
        if unmapped:
            with st.expander(f"Unmapped rows ({len(unmapped)})"):
                st.dataframe(pd.DataFrame(unmapped, columns=["Master row", "Survey number"]), hide_index=True)
            st.warning("Unmapped rows will be skipped. The output order follows the master list. Select at least one source page to create the PDF.")

        # Generate output: mapped pages in master-list order. If no mappings yet,
        # provide a valid fallback PDF (the uploaded original) so the PDF download
        # control remains visible and usable rather than disappearing/being disabled.
        output_pdf = None
        export_label = "⬇️ Download Sequenced PDF"
        if mapped:
            out = pymupdf.open()
            for _, _, page_choice in mapped:
                page_no = int(page_choice.replace("Page ", "")) - 1
                out.insert_pdf(doc, from_page=page_no, to_page=page_no)
            output_pdf = out.tobytes(garbage=4, deflate=True)
            out.close()
        else:
            output_pdf = pdf_bytes
            export_label = "⬇️ Download PDF (Original — no pages mapped yet)"
            st.warning("No pages mapped yet. The PDF button will download the original PDF until you map at least one master-list row.")

        st.subheader("Step 3 — Download output")
        st.download_button(
            label=export_label,
            data=output_pdf,
            file_name="survey_numbers_sequenced.pdf" if mapped else "original_pdf_unmapped.pdf",
            mime="application/pdf",
            key="download_sequenced_pdf",
            help="Mapped rows export in master-list order. If nothing is mapped, this downloads the original PDF."
        )
        audit = pd.DataFrame({
            "Master row": range(1, len(master)+1),
            "Survey number": master,
            "Selected source page": st.session_state.mapping_values
        })
        st.download_button("⬇️ Download Mapping CSV", audit.to_csv(index=False).encode("utf-8-sig"),
                           "survey_page_mapping.csv", "text/csv", key="download_mapping_csv")

        st.subheader("Optional page preview")
        preview_page = st.selectbox("Choose source page to preview", range(1, len(doc)+1), format_func=lambda n: f"Page {n}")
        pix = doc[preview_page-1].get_pixmap(matrix=pymupdf.Matrix(1.1, 1.1), alpha=False)
        st.image(pix.tobytes("png"), caption=f"Original PDF page {preview_page}")
        doc.close()
    except Exception as e:
        st.error(f"Error processing PDF: {e}")
elif pdf_file and not master:
    st.warning("Paste the master list to enable the mapping and export area.")
else:
    st.info("Upload your PDF and paste your master survey list to start.")
