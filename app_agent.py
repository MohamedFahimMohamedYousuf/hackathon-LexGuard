"""
LexGuard — Streamlit UI (Agent version)
Run with: streamlit run app_agent.py
"""

import json
import streamlit as st
from orchestrator import run_pipeline
from agent_state import AgentStatus

st.set_page_config(page_title="LexGuard", page_icon="⚖️", layout="wide")

# ── Session state defaults ────────────────────────────────────────────────
# Initialise ALL session state keys upfront before ANY rendering happens.
# This is critical — sidebar reads from these keys, main page writes to them.

if "agent_statuses" not in st.session_state:
    st.session_state.agent_statuses = {
        "Document Ingestion":  AgentStatus.PENDING,
        "Metadata Extraction": AgentStatus.PENDING,
        "Clause Comparison":   AgentStatus.PENDING,
        "Risk Classification": AgentStatus.PENDING,
        "Report Generation":   AgentStatus.PENDING,
    }

if "pipeline_json" not in st.session_state:
    st.session_state.pipeline_json = None

if "show_json" not in st.session_state:
    st.session_state.show_json = False

if "pipeline_ran" not in st.session_state:
    st.session_state.pipeline_ran = False

# ── Constants ─────────────────────────────────────────────────────────────
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

# ══════════════════════════════════════════════════════════════════════════
# SIDEBAR — reads from session_state (always up to date)
# ══════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### ⚖️ LexGuard")
    st.caption("Multi-Agent Contract Review System")
    st.divider()

    # ── Pipeline Status ───────────────────────────────────────────────────
    st.markdown("#### 🔁 Pipeline Status")

    for agent_name, status in st.session_state.agent_statuses.items():
        icon  = STATUS_ICON.get(status, "⚪")
        label = STATUS_LABEL.get(status, "Pending")
        st.markdown(
            f"{icon} &nbsp; **{agent_name}**  \n"
            f"<span style='font-size:11px;color:gray;padding-left:24px'>{label}</span>",
            unsafe_allow_html=True,
        )
        st.markdown("<div style='margin-bottom:4px'></div>", unsafe_allow_html=True)

    st.caption("Agents run in sequence. Each one unlocks the next.")
    st.divider()

    # ── Pipeline State JSON — only shown after pipeline has run ───────────
    if st.session_state.pipeline_json is not None:
        st.markdown("#### 🗂️ Pipeline State JSON")
        st.caption("Live state passed between agents")

        if st.button("Show / Hide JSON", use_container_width=True):
            st.session_state.show_json = not st.session_state.show_json

        if st.session_state.show_json:
            json_section = st.radio(
                "View section",
                ["Summary", "Clauses", "Pages", "Full JSON"],
                label_visibility="collapsed",
            )
            data = st.session_state.pipeline_json

            if json_section == "Summary":
                st.json({k: v for k, v in data.items()
                         if k not in ("full_text", "pages", "clause_segments")})

            elif json_section == "Clauses":
                st.json([
                    {"id": c["id"], "heading": c["heading"],
                     "clause_type": c["clause_type"], "chars": c["char_count"]}
                    for c in data.get("clause_segments", [])
                ])

            elif json_section == "Pages":
                st.json([
                    {"page": p["page_number"], "chars": p["char_count"],
                     "scanned": p["is_scanned"],
                     "preview": p["text"][:80] + "..." if len(p["text"]) > 80 else p["text"]}
                    for p in data.get("pages", [])
                ])

            elif json_section == "Full JSON":
                display = dict(data)
                if display.get("full_text"):
                    display["full_text"] = display["full_text"][:300] + "... [truncated]"
                display["clause_segments"] = display.get("clause_segments", [])[:3]
                display["_note"] = "clause_segments truncated to first 3 for display"
                st.json(display)

        st.divider()
        st.download_button(
            "⬇ Download full JSON",
            data=json.dumps(st.session_state.pipeline_json, indent=2),
            file_name="pipeline_state.json",
            mime="application/json",
            use_container_width=True,
        )
    else:
        st.caption("Upload a contract to see the pipeline JSON here.")


# ══════════════════════════════════════════════════════════════════════════
# MAIN PAGE
# ══════════════════════════════════════════════════════════════════════════
st.title("⚖️ LexGuard")
st.caption("Multi-Agent Contract Review System — Document Ingestion Agent")
st.divider()

uploaded_file = st.file_uploader(
    "Upload a contract PDF",
    type=["pdf"],
    help="Text-based PDFs up to 20 MB. No password-protected files.",
)

if not uploaded_file:
    # Reset if user clears the file
    if st.session_state.pipeline_ran:
        st.session_state.pipeline_ran = False
        st.session_state.pipeline_json = None
        st.session_state.agent_statuses = {k: AgentStatus.PENDING for k in st.session_state.agent_statuses}
    st.info("Upload a contract PDF. The Ingestion Agent will validate, extract, and hand off to the pipeline.")
    st.stop()

# ── Run pipeline only once per upload ────────────────────────────────────
# Use file name + size as a cache key so re-renders don't re-run the pipeline
file_key = f"{uploaded_file.name}_{uploaded_file.size}"

if st.session_state.get("last_file_key") != file_key:
    # New file uploaded — run the pipeline
    st.session_state.last_file_key = file_key
    st.session_state.pipeline_ran  = False

if not st.session_state.pipeline_ran:
    # Mark ingestion as running first so sidebar updates
    st.session_state.agent_statuses["Document Ingestion"] = AgentStatus.RUNNING

    file_bytes = uploaded_file.read()

    with st.spinner("Ingestion Agent running..."):
        state = run_pipeline(file_bytes, uploaded_file.name)

    # ── Write ALL results into session_state so sidebar can read them ─────
    st.session_state.agent_statuses["Document Ingestion"]  = state.ingestion_status
    st.session_state.agent_statuses["Metadata Extraction"] = state.metadata_status
    st.session_state.agent_statuses["Clause Comparison"]   = state.clause_status
    st.session_state.agent_statuses["Risk Classification"] = state.risk_status
    st.session_state.agent_statuses["Report Generation"]   = state.report_status

    st.session_state.pipeline_json = {
        "file_name":                state.file_name,
        "doc_hash":                 state.doc_hash,
        "ingestion_status":         state.ingestion_status.value,
        "contract_type":            state.contract_type,
        "contract_type_confidence": state.contract_type_confidence,
        "contract_type_method":     state.contract_type_method,
        "page_count":               state.page_count,
        "file_size_kb":             state.file_size_kb,
        "scanned_pages":            state.scanned_pages,
        "warnings":                 state.ingestion_warnings,
        "clause_segments": [
            {k: v for k, v in c.items()} for c in state.clause_segments
        ],
        "full_text":                state.full_text,
        "pages": [
            {"page_number": p.page_number, "text": p.text,
             "char_count": p.char_count,   "is_scanned": p.is_scanned}
            for p in state.pages
        ],
    }
    st.session_state.pipeline_state = state
    st.session_state.pipeline_ran   = True

    # Rerun so sidebar re-renders with updated session_state values
    st.rerun()

# ── From here, read results from session_state (not re-running pipeline) ──
state  = st.session_state.pipeline_state
output = st.session_state.pipeline_json

# ── Agent status banner ───────────────────────────────────────────────────
if state.ingestion_status == AgentStatus.FAILED:
    st.error(f"Ingestion Agent FAILED: {state.ingestion_error}")
    st.stop()
elif state.ingestion_status == AgentStatus.NEEDS_OCR:
    st.warning(f"Scanned pages detected: {state.scanned_pages}. OCR agent will handle these.")
elif state.ingestion_status == AgentStatus.COMPLETED:
    st.success("Ingestion Agent completed successfully. Ready for next agent.")

# ── Metrics ───────────────────────────────────────────────────────────────
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Pages",         state.page_count)
col2.metric("File size",     f"{state.file_size_kb} KB")
col3.metric("Total chars",   f"{len(state.full_text):,}")
found_n = sum(1 for c in state.clause_segments if c.get("found"))
col4.metric("Clauses found", f"{found_n}/{len(state.clause_segments)}")
col5.metric("Scanned pages", len(state.scanned_pages))
st.caption(f"Document hash (SHA-256): `{state.doc_hash}`")

# ── Contract type ─────────────────────────────────────────────────────────
CONFIDENCE_COLOR = {"high": "🟢", "medium": "🟡", "low": "🔴"}
conf_icon = CONFIDENCE_COLOR.get(state.contract_type_confidence, "⚪")
st.markdown(
    f"**Contract type detected:** `{state.contract_type}` &nbsp; "
    f"{conf_icon} **{state.contract_type_confidence.upper()}** confidence &nbsp; "
    f"*(method: {state.contract_type_method})*"
)

# ── Warnings ──────────────────────────────────────────────────────────────
if state.ingestion_warnings:
    with st.expander(f"⚠️ {len(state.ingestion_warnings)} warning(s)"):
        for w in state.ingestion_warnings:
            st.warning(w)

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["📄 Extracted text", "🔍 Clause segments"])

with tab1:
    view = st.radio("View", ["Full document", "Page by page"],
                    horizontal=True, label_visibility="collapsed")
    if view == "Full document":
        st.text_area("Full document text",
                     value=state.clean_text or state.full_text,
                     height=500, label_visibility="collapsed")
    else:
        selected = st.selectbox("Select page",
                                [p.page_number for p in state.pages],
                                format_func=lambda x: f"Page {x}")
        page = next(p for p in state.pages if p.page_number == selected)
        if page.is_scanned:
            st.warning("Scanned page — OCR needed for full text.")
        st.text_area("Page text",
                     value=page.text or "(No text detected)",
                     height=400, label_visibility="collapsed")
        st.caption(f"Characters: {page.char_count:,}")

with tab2:
    if not state.clause_segments:
        st.info("No clause data available.")
    else:
        found_count   = sum(1 for c in state.clause_segments if c.get("found"))
        missing_count = len(state.clause_segments) - found_count

        # Summary bar
        col_f, col_m, col_t = st.columns(3)
        col_f.metric("✅ Found",   found_count)
        col_m.metric("❌ Missing", missing_count)
        col_t.metric("📋 Total",  len(state.clause_segments))
        st.caption(f"Checked against **{state.contract_type}** standard clause library")
        st.divider()

        RISK_BADGE  = {"HIGH": "🔴 HIGH", "MEDIUM": "🟡 MEDIUM", "LOW": "🟢 LOW"}
        CAT_ICON    = {
            "confidentiality": "🔵", "liability": "🔴", "termination": "🟠",
            "jurisdiction": "🟣",    "ip": "🟡",         "payment": "🟢",
            "performance": "🔵",     "compliance": "🟤", "governance": "🟤",
            "financial": "🟢",       "security": "🔴",   "term": "⚪",
            "data_handling": "🔵",   "legal": "🟣",      "legal_remedy": "🟣",
            "monitoring": "🔵",      "operations": "⚪", "penalty": "🔴",
            "support": "🟢",         "exclusions": "⚪", "structure": "⚪",
            "ownership": "🟡",       "restrictive_covenant": "🟠",
            "exit": "🟠",            "general": "⚪",
        }

        for clause in state.clause_segments:
            found     = clause.get("found", False)
            canonical = clause["canonical_title"]
            category  = clause["category"]
            risk      = clause.get("risk_weight", "MEDIUM")
            raw       = clause.get("raw_heading", "")
            cat_icon  = CAT_ICON.get(category, "⚪")
            status    = "✅ Found" if found else "❌ Missing"

            # Expander label — canonical title + found/missing
            label = f"{status} — {canonical}  [{category.replace('_', ' ').title()}]"

            with st.expander(label, expanded=False):
                c1, c2, c3 = st.columns(3)
                c1.markdown(f"**Risk weight:** {RISK_BADGE.get(risk, risk)}")
                c2.markdown(f"**Category:** {cat_icon} {category.replace('_',' ').title()}")
                c3.markdown(f"**Document heading:** `{raw}`")