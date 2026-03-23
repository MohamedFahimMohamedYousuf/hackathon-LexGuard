"""
LexGuard — Streamlit UI (Agent version)
Calls the Orchestrator which calls the Document Ingestion Agent.
Run with: streamlit run app.py
"""

import json
import streamlit as st
from orchestrator import run_pipeline
from agent_state import AgentStatus

st.set_page_config(page_title="LexGuard", page_icon="⚖️", layout="wide")

# ── Sidebar — always visible ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚖️ LexGuard")
    st.caption("Multi-Agent Contract Review System")
    st.divider()
    st.markdown("#### 🔁 Pipeline Status")

    # We use session_state to persist agent statuses across reruns
    if "agent_statuses" not in st.session_state:
        st.session_state.agent_statuses = {
            "Document Ingestion":   AgentStatus.PENDING,
            "Metadata Extraction":  AgentStatus.PENDING,
            "Clause Comparison":    AgentStatus.PENDING,
            "Risk Classification":  AgentStatus.PENDING,
            "Report Generation":    AgentStatus.PENDING,
        }

    STATUS_ICON = {
        AgentStatus.COMPLETED: "🟢",
        AgentStatus.RUNNING:   "🔵",
        AgentStatus.NEEDS_OCR: "🟡",
        AgentStatus.FAILED:    "🔴",
        AgentStatus.PENDING:   "⚪",
    }
    STATUS_LABEL = {
        AgentStatus.COMPLETED: "Completed",
        AgentStatus.RUNNING:   "Running...",
        AgentStatus.NEEDS_OCR: "Needs OCR",
        AgentStatus.FAILED:    "Failed",
        AgentStatus.PENDING:   "Pending",
    }

    for agent_name, status in st.session_state.agent_statuses.items():
        icon  = STATUS_ICON.get(status, "⚪")
        label = STATUS_LABEL.get(status, "Pending")
        st.markdown(
            f"{icon} &nbsp; **{agent_name}**  \n"
            f"<span style='font-size:11px; color:gray; padding-left:24px'>{label}</span>",
            unsafe_allow_html=True,
        )
        st.markdown("<div style='margin-bottom:6px'></div>", unsafe_allow_html=True)

    st.divider()
    st.caption("Agents run in sequence. Each one unlocks the next.")

    # ── Pipeline State JSON Viewer ───────────────────────────────────────
    if "pipeline_json" in st.session_state:
        st.markdown("#### 🗂️ Pipeline State JSON")
        st.caption("Live state passed between agents")

        # Toggle button
        if "show_json" not in st.session_state:
            st.session_state.show_json = False

        if st.button("Show / Hide JSON", use_container_width=True):
            st.session_state.show_json = not st.session_state.show_json

        if st.session_state.show_json:
            # Section tabs inside sidebar
            json_section = st.radio(
                "View section",
                ["Summary", "Pages", "Full JSON"],
                horizontal=False,
                label_visibility="collapsed",
            )

            data = st.session_state.pipeline_json

            if json_section == "Summary":
                summary = {k: v for k, v in data.items() if k not in ("full_text", "pages")}
                st.json(summary)

            elif json_section == "Pages":
                pages_data = [
                    {
                        "page": p["page_number"],
                        "chars": p["char_count"],
                        "scanned": p["is_scanned"],
                        "preview": p["text"][:80] + "..." if len(p["text"]) > 80 else p["text"],
                    }
                    for p in data.get("pages", [])
                ]
                st.json(pages_data)

            elif json_section == "Full JSON":
                # Show full JSON but truncate full_text for readability
                display = dict(data)
                if display.get("full_text"):
                    display["full_text"] = display["full_text"][:200] + "... [truncated]"
                st.json(display)

        st.divider()
        # Download button in sidebar too
        st.download_button(
            "⬇ Download JSON",
            data=json.dumps(st.session_state.pipeline_json, indent=2),
            file_name="pipeline_state.json",
            mime="application/json",
            use_container_width=True,
        )

# ── Main page ────────────────────────────────────────────────────────────
st.title("⚖️ LexGuard")
st.caption("Multi-Agent Contract Review System — Document Ingestion Agent")
st.divider()

uploaded_file = st.file_uploader(
    "Upload a contract PDF",
    type=["pdf"],
    help="Text-based PDFs up to 20 MB. No password-protected files.",
)

if not uploaded_file:
    st.info("Upload a contract PDF. The Ingestion Agent will validate, extract, and hand off to the pipeline.")
    st.stop()

file_bytes = uploaded_file.read()

# Mark ingestion as running in sidebar before we start
st.session_state.agent_statuses["Document Ingestion"] = AgentStatus.RUNNING
st.rerun() if False else None  # sidebar updates on next interaction; spinner handles UX

with st.spinner("Ingestion Agent running..."):
    state = run_pipeline(file_bytes, uploaded_file.name)

# Update sidebar with real statuses from pipeline state
st.session_state.agent_statuses["Document Ingestion"]  = state.ingestion_status
st.session_state.agent_statuses["Metadata Extraction"] = state.metadata_status
st.session_state.agent_statuses["Clause Comparison"]   = state.clause_status
st.session_state.agent_statuses["Risk Classification"] = state.risk_status
st.session_state.agent_statuses["Report Generation"]   = state.report_status

# ── Agent status banner ──────────────────────────────────────────────────
if state.ingestion_status == AgentStatus.FAILED:
    st.error(f"Ingestion Agent FAILED: {state.ingestion_error}")
    st.stop()

elif state.ingestion_status == AgentStatus.NEEDS_OCR:
    st.warning(
        f"Ingestion Agent completed with warnings. "
        f"Scanned pages detected: {state.scanned_pages}. "
        "OCR agent will be triggered for these pages."
    )

elif state.ingestion_status == AgentStatus.COMPLETED:
    st.success("Ingestion Agent completed successfully. Ready for next agent.")

# ── Metrics ──────────────────────────────────────────────────────────────
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Pages", state.page_count)
col2.metric("File size", f"{state.file_size_kb} KB")
col3.metric("Total chars", f"{len(state.full_text):,}")
col4.metric("Clauses found", len(state.clause_segments))
col5.metric("Scanned pages", len(state.scanned_pages))
st.caption(f"Document hash (SHA-256): `{state.doc_hash}`")

# ── Contract type detection result ───────────────────────────────────────
CONFIDENCE_COLOR = {"high": "🟢", "medium": "🟡", "low": "🔴"}
icon = CONFIDENCE_COLOR.get(state.contract_type_confidence, "⚪")
st.markdown(
    f"**Contract type detected:** `{state.contract_type}` &nbsp; "
    f"{icon} {state.contract_type_confidence.upper()} confidence &nbsp; "
    f"*(method: {state.contract_type_method})*"
)

# ── Warnings ─────────────────────────────────────────────────────────────
if state.ingestion_warnings:
    with st.expander(f"⚠️ {len(state.ingestion_warnings)} warning(s)"):
        for w in state.ingestion_warnings:
            st.warning(w)

st.divider()

# ── Tabs: Extracted text | Clause segments ───────────────────────────────
tab1, tab2 = st.tabs(["📄 Extracted text", "🔍 Clause segments"])

with tab1:
    view = st.radio("View", ["Full document", "Page by page"], horizontal=True, label_visibility="collapsed")
    if view == "Full document":
        st.text_area("Full document text", value=state.clean_text or state.full_text, height=500, label_visibility="collapsed")
    else:
        selected = st.selectbox("Select page", [p.page_number for p in state.pages], format_func=lambda x: f"Page {x}")
        page = next(p for p in state.pages if p.page_number == selected)
        if page.is_scanned:
            st.warning("Scanned page — OCR needed for full text.")
        st.text_area("Page text", value=page.text or "(No text detected)", height=400, label_visibility="collapsed")
        st.caption(f"Characters: {page.char_count:,}")

with tab2:
    if not state.clause_segments:
        st.info("No clause segments detected.")
    else:
        CLAUSE_TYPE_COLORS = {
            "confidentiality": "🔵", "liability": "🔴", "termination": "🟠",
            "governing_law": "🟣", "dispute_resolution": "🟤", "ip_ownership": "🟡",
            "payment": "🟢", "term": "⚪", "renewal": "🔵", "warranties": "🟡",
            "force_majeure": "⚫", "general": "⚪",
        }
        for clause in state.clause_segments:
            icon = CLAUSE_TYPE_COLORS.get(clause["clause_type"], "⚪")
            with st.expander(
                f"{icon} Clause {clause['id']} — {clause['heading']} "
                f"[{clause['clause_type'].replace('_',' ').title()}]"
            ):
                st.text(clause["text"])
                st.caption(f"Level: {clause['level']} | Characters: {clause['char_count']}")

st.divider()

# ── Build + store pipeline state JSON (feeds sidebar viewer) ─────────────
output = {
    "file_name": state.file_name,
    "doc_hash": state.doc_hash,
    "ingestion_status": state.ingestion_status.value,
    "contract_type": state.contract_type,
    "contract_type_confidence": state.contract_type_confidence,
    "page_count": state.page_count,
    "file_size_kb": state.file_size_kb,
    "scanned_pages": state.scanned_pages,
    "warnings": state.ingestion_warnings,
    "clause_segments": state.clause_segments,
    "full_text": state.full_text,
    "pages": [
        {
            "page_number": p.page_number,
            "text": p.text,
            "char_count": p.char_count,
            "is_scanned": p.is_scanned,
        }
        for p in state.pages
    ],
}
st.session_state.pipeline_json = output
st.info("Open the sidebar (top-left ▶) to inspect the live pipeline state JSON.", icon="🗂️")