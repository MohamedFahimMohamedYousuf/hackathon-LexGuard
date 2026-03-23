"""
LexGuard — Document Ingestion Agent  (Complete — all 5 steps)

Role        : First agent in the pipeline
Responsibility:
    Step 1 — PDF Extraction        : parse PDF → raw text per page
    Step 2 — Cleaning & Normalisation : strip noise, fix whitespace
    Step 3 — Contract Type Detection  : NDA / SLA / Vendor / Partnership
    Step 4 — Clause Structure Detection : find numbered headings + hierarchy
    Step 5 — Clause Segmentation      : split into individual clause objects

LLM usage   : NO LLM in this agent.
              Contract type detection uses keyword matching (fast, free, offline).
              LLM is used from Agent 2 (Metadata Extraction) onwards.

Input  : PipelineState with file_bytes + file_name
Output : PipelineState with ingestion_status = COMPLETED / NEEDS_OCR / FAILED
"""

import hashlib
import re
import logging
from agent_state import PipelineState, AgentStatus, PageData

logger = logging.getLogger(__name__)

AGENT_NAME        = "DocumentIngestionAgent"
MAX_SIZE_MB       = 20
SCANNED_THRESHOLD = 50


# ══════════════════════════════════════════════════════════════════════════
# CONTRACT TYPE DETECTION CONFIG
# Each type has:
#   primary   — strong signals (title-level keywords) → HIGH confidence
#   secondary — supporting signals                    → MEDIUM confidence
# ══════════════════════════════════════════════════════════════════════════

CONTRACT_SIGNATURES = {
    "NDA": {
        "primary":   [
            r"\bnon[\s-]?disclosure\b",
            r"\bconfidentiality agreement\b",
            r"\bnda\b",
        ],
        "secondary": [
            r"\bconfidential information\b",
            r"\bdisclosing party\b",
            r"\breceiving party\b",
            r"\bproprietary information\b",
        ],
    },
    "SLA": {
        "primary":   [
            r"\bservice level agreement\b",
            r"\bsla\b",
            r"\bservice level\b",
        ],
        "secondary": [
            r"\buptime\b",
            r"\bresponse time\b",
            r"\bservice credits?\b",
            r"\bavailability\b",
            r"\bincident\b",
        ],
    },
    "VENDOR": {
        "primary":   [
            r"\bvendor agreement\b",
            r"\bvendor services?\b",
            r"\bsupplier agreement\b",
            r"\bprocurement agreement\b",
        ],
        "secondary": [
            r"\bpurchase order\b",
            r"\bdeliverables?\b",
            r"\bvendor\b",
            r"\bsupplier\b",
            r"\bstatement of work\b",
        ],
    },
    "PARTNERSHIP": {
        "primary":   [
            r"\bpartnership agreement\b",
            r"\bjoint venture\b",
            r"\bstrategic alliance\b",
        ],
        "secondary": [
            r"\bpartner\b",
            r"\bco[\s-]?operation\b",
            r"\bprofit sharing\b",
            r"\bjoint\b",
            r"\bcollaboration\b",
        ],
    },
}

# Clause type keyword map — used in Step 5 to label each clause
CLAUSE_TYPE_KEYWORDS = {
    "confidentiality":    [r"\bconfidential", r"\bnon[\s-]?disclosure"],
    "liability":          [r"\bliabilit", r"\bindemnif", r"\bdamages\b"],
    "termination":        [r"\btermination\b", r"\bterminate\b", r"\bexpir"],
    "governing_law":      [r"\bgoverning law\b", r"\bjurisdiction\b", r"\bchoice of law\b"],
    "dispute_resolution": [r"\bdispute\b", r"\barbitration\b", r"\bmediation\b"],
    "ip_ownership":       [r"\bintellectual property\b", r"\bip\b", r"\bcopyright\b", r"\bpatent\b"],
    "payment":            [r"\bpayment\b", r"\binvoice\b", r"\bfees?\b", r"\bcompensation\b"],
    "term":               [r"\bterm\b", r"\bduration\b", r"\bperiod\b"],
    "renewal":            [r"\brenewal\b", r"\bauto[\s-]?renew", r"\brenew\b"],
    "warranties":         [r"\bwarrant", r"\brepresentation\b"],
    "force_majeure":      [r"\bforce majeure\b", r"\bact of god\b"],
    "general":            [],   # fallback
}


# ══════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════

def run(state: PipelineState) -> PipelineState:
    logger.info(f"[{AGENT_NAME}] Starting → {state.file_name}")
    state.ingestion_status = AgentStatus.RUNNING

    # ── Step 1: Extract raw text ──────────────────────────────────────
    error = _validate(state)
    if error:
        return _fail(state, error)
    try:
        _extract_raw(state)
    except Exception as e:
        return _fail(state, f"Extraction failed: {e}")

    # ── Step 2: Clean & normalise ─────────────────────────────────────
    _clean_and_normalise(state)

    # ── Step 3: Contract type detection ──────────────────────────────
    _detect_contract_type(state)

    # ── Step 4 + 5: Clause structure detection + segmentation ────────
    _segment_clauses(state)

    # ── Final status decision ─────────────────────────────────────────
    if state.scanned_pages:
        logger.warning(f"[{AGENT_NAME}] Scanned pages: {state.scanned_pages} → NEEDS_OCR")
        state.ingestion_status = AgentStatus.NEEDS_OCR
    else:
        state.ingestion_status = AgentStatus.COMPLETED

    logger.info(
        f"[{AGENT_NAME}] Done | Status={state.ingestion_status.value} | "
        f"Type={state.contract_type} ({state.contract_type_confidence}) | "
        f"Pages={state.page_count} | Clauses={len(state.clause_segments)}"
    )
    return state


# ══════════════════════════════════════════════════════════════════════════
# STEP 1 — VALIDATE + EXTRACT RAW TEXT
# ══════════════════════════════════════════════════════════════════════════

def _validate(state: PipelineState) -> str | None:
    file_bytes = state.file_bytes
    state.file_size_kb = round(len(file_bytes) / 1024, 2)

    if len(file_bytes) / (1024 * 1024) > MAX_SIZE_MB:
        return f"File too large. Max: {MAX_SIZE_MB} MB."
    if not file_bytes.startswith(b"%PDF"):
        return "Not a valid PDF (missing %PDF header)."
    try:
        import fitz
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        return f"Cannot open PDF: {e}"
    if doc.is_encrypted:
        doc.close()
        return "PDF is password-protected."
    if doc.page_count == 0:
        doc.close()
        return "PDF has no pages."
    doc.close()
    state.doc_hash = hashlib.sha256(file_bytes).hexdigest()
    return None


def _extract_raw(state: PipelineState) -> None:
    import fitz
    doc = fitz.open(stream=state.file_bytes, filetype="pdf")
    state.page_count = doc.page_count
    pages, parts, scanned, warnings = [], [], [], []

    for i in range(doc.page_count):
        raw   = doc[i].get_text("text")
        chars = len(raw.strip())
        is_sc = chars < SCANNED_THRESHOLD
        if is_sc:
            scanned.append(i + 1)
            warnings.append(f"Page {i+1} has {chars} chars — likely scanned.")
        pages.append(PageData(page_number=i+1, text=raw, char_count=chars, is_scanned=is_sc))
        parts.append(raw)

    doc.close()
    state.pages              = pages
    state.scanned_pages      = scanned
    state.ingestion_warnings = warnings
    state.full_text          = "\n\n--- PAGE BREAK ---\n\n".join(parts)


# ══════════════════════════════════════════════════════════════════════════
# STEP 2 — CLEANING & NORMALISATION
# ══════════════════════════════════════════════════════════════════════════

def _clean_and_normalise(state: PipelineState) -> None:
    """
    Produces state.clean_text — a normalised version of full_text used
    for contract type detection and clause segmentation.
    Transformations:
      - Remove page headers/footers (short repeated lines)
      - Collapse excessive whitespace
      - Normalise unicode quotes and dashes
      - Remove page break markers
    """
    text = state.full_text

    # Remove page break markers we inserted
    text = text.replace("--- PAGE BREAK ---", "")

    # Normalise unicode punctuation
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2013", "-").replace("\u2014", "-")

    # Remove lines that are just page numbers (e.g. "- 3 -" or "Page 3")
    text = re.sub(r'(?m)^[\s]*[-–]?\s*[Pp]age\s+\d+\s*[-–]?\s*$', '', text)
    text = re.sub(r'(?m)^\s*\d+\s*$', '', text)

    # Collapse 3+ newlines → 2
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Strip trailing spaces per line
    text = "\n".join(line.rstrip() for line in text.splitlines())

    state.clean_text = text.strip()


# ══════════════════════════════════════════════════════════════════════════
# STEP 3 — CONTRACT TYPE DETECTION (keyword-based, no LLM)
# ══════════════════════════════════════════════════════════════════════════

def _detect_contract_type(state: PipelineState) -> None:
    """
    Detects contract type purely from document CONTENT (clean_text).
    Filename is NOT used for scoring — it is only logged for debug.

    Why not filename?
      - A file named "nda_draft.pdf" could contain a Vendor Agreement
      - A file named "contract_final_v3.pdf" gives no signal at all
      - Filename is user-controlled and unreliable
      - Document content is the ground truth

    Scoring (content only):
      - Each primary keyword match   = 10 points  (title-level signals)
      - Each secondary keyword match =  2 points  (supporting signals)

    Confidence:
      - winner score >= 10 AND > 2x runner-up score  → HIGH
      - winner score >= 6                             → MEDIUM
      - anything else                                 → LOW

    Filename is used ONLY as a tiebreaker when two types have equal scores.
    """
    text_lower  = state.clean_text.lower()
    fname_lower = state.file_name.lower()  # debug/tiebreaker only

    scores: dict[str, int] = {}

    for contract_type, sigs in CONTRACT_SIGNATURES.items():
        score = 0
        # Primary signals — content only
        for pattern in sigs["primary"]:
            if re.search(pattern, text_lower):
                score += 10
        # Secondary signals — content only
        for pattern in sigs["secondary"]:
            if re.search(pattern, text_lower):
                score += 2
        scores[contract_type] = score

    logger.info(f"[{AGENT_NAME}] Content scores: {scores} | filename hint: {fname_lower}")

    # Find winner by content score
    winner       = max(scores, key=scores.get)
    winner_score = scores[winner]

    # All scores zero → content gave no signal
    if winner_score == 0:
        # Last resort: check filename as a weak hint (1 point only, not stored in scores)
        for contract_type, sigs in CONTRACT_SIGNATURES.items():
            for pattern in sigs["primary"]:
                if re.search(pattern, fname_lower):
                    logger.warning(
                        f"[{AGENT_NAME}] Content gave no signal. "
                        f"Filename suggests {contract_type} — using as LOW confidence hint."
                    )
                    state.contract_type            = contract_type
                    state.contract_type_confidence = "low"
                    state.contract_type_method     = "filename_fallback"
                    return

        state.contract_type            = "UNKNOWN"
        state.contract_type_confidence = "low"
        state.contract_type_method     = "keyword"
        logger.warning(f"[{AGENT_NAME}] Could not detect contract type from content or filename.")
        return

    # Tiebreaker: if top two types have equal content scores, use filename to pick
    sorted_scores = sorted(scores.values(), reverse=True)
    runner_up     = sorted_scores[1] if len(sorted_scores) > 1 else 0

    if winner_score == runner_up:
        for contract_type, sigs in CONTRACT_SIGNATURES.items():
            for pattern in sigs["primary"]:
                if re.search(pattern, fname_lower) and scores[contract_type] == winner_score:
                    logger.info(f"[{AGENT_NAME}] Tie broken by filename → {contract_type}")
                    winner = contract_type
                    break

    # Confidence based on content score margin only
    if winner_score >= 10 and winner_score > (runner_up * 2):
        confidence = "high"
    elif winner_score >= 6:
        confidence = "medium"
    else:
        confidence = "low"

    state.contract_type            = winner
    state.contract_type_confidence = confidence
    state.contract_type_method     = "keyword"
    logger.info(f"[{AGENT_NAME}] Contract type → {winner} (confidence: {confidence})")


# ══════════════════════════════════════════════════════════════════════════
# STEP 4 + 5 — CLAUSE STRUCTURE DETECTION + SEGMENTATION
# ══════════════════════════════════════════════════════════════════════════

# Patterns for clause headings — ordered from most specific to least
HEADING_PATTERNS = [
    # "1.2.3  Heading Text" or "1.2 Heading Text"
    (r'^\s*(\d+\.\d+(?:\.\d+)?)\s{1,6}([A-Z][^\n]{2,60})', 2),
    # "1. HEADING TEXT" or "1. Heading Text"
    (r'^\s*(\d+)\.\s{1,4}([A-Z][^\n]{2,60})', 1),
    # "ARTICLE 1 — HEADING" or "SECTION 1:"
    (r'^\s*(ARTICLE|SECTION|CLAUSE)\s+(\d+[\.\d]*)[:\s–-]+([A-Z][^\n]{2,60})', 1),
    # ALL CAPS heading (no number) — treated as level 1
    (r'^\s*([A-Z][A-Z\s]{4,50})$', 1),
]


def _segment_clauses(state: PipelineState) -> None:
    """
    Steps 4 + 5 combined:
    - Detects clause headings by pattern matching
    - Splits text into clause segments
    - Labels each clause with a clause_type
    """
    lines  = state.clean_text.splitlines()
    clauses: list[dict] = []
    current_heading  = "Preamble"
    current_level    = 0
    current_lines: list[str] = []
    clause_id = 1

    def flush(heading, level, body_lines, cid):
        body = "\n".join(body_lines).strip()
        if not body and not heading:
            return
        clauses.append({
            "id":          cid,
            "heading":     heading,
            "text":        body,
            "level":       level,
            "clause_type": _classify_clause_type(heading + " " + body),
            "char_count":  len(body),
        })

    for line in lines:
        matched = False
        for pattern, level in HEADING_PATTERNS:
            m = re.match(pattern, line)
            if m:
                # Save previous clause
                flush(current_heading, current_level, current_lines, clause_id)
                clause_id += 1
                # Start new clause
                groups = m.groups()
                # Extract heading text from last non-empty group
                current_heading = groups[-1].strip()
                current_level   = level
                current_lines   = []
                matched = True
                break

        if not matched:
            current_lines.append(line)

    # Flush last clause
    flush(current_heading, current_level, current_lines, clause_id)

    # Filter out empty/trivial clauses
    state.clause_segments = [c for c in clauses if c["char_count"] > 20]
    logger.info(f"[{AGENT_NAME}] Segmented {len(state.clause_segments)} clauses")


def _classify_clause_type(text: str) -> str:
    """Label a clause by scanning its text against the keyword map."""
    text_lower = text.lower()
    for clause_type, patterns in CLAUSE_TYPE_KEYWORDS.items():
        if clause_type == "general":
            continue
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return clause_type
    return "general"


# ══════════════════════════════════════════════════════════════════════════
# HELPER
# ══════════════════════════════════════════════════════════════════════════

def _fail(state: PipelineState, error: str) -> PipelineState:
    logger.error(f"[{AGENT_NAME}] FAILED — {error}")
    state.ingestion_status = AgentStatus.FAILED
    state.ingestion_error  = error
    return state