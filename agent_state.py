"""
LexGuard — Shared Pipeline State
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class AgentStatus(str, Enum):
    PENDING    = "PENDING"
    RUNNING    = "RUNNING"
    COMPLETED  = "COMPLETED"
    NEEDS_OCR  = "NEEDS_OCR"
    FAILED     = "FAILED"


@dataclass
class PageData:
    page_number: int
    text: str
    char_count: int
    is_scanned: bool


@dataclass
class PipelineState:
    """Shared state baton passed between every agent."""

    # ── Input ────────────────────────────────────────────────────
    file_bytes: bytes = field(default_factory=bytes)
    file_name: str = ""

    # ── Ingestion Agent outputs ──────────────────────────────────
    ingestion_status: AgentStatus = AgentStatus.PENDING
    ingestion_error: Optional[str] = None
    doc_hash: Optional[str] = None
    page_count: int = 0
    file_size_kb: float = 0.0
    full_text: str = ""           # Raw joined text
    clean_text: str = ""          # Normalised text after cleaning
    pages: list[PageData] = field(default_factory=list)
    scanned_pages: list[int] = field(default_factory=list)
    ingestion_warnings: list[str] = field(default_factory=list)

    # ── Contract type detection ──────────────────────────────────
    contract_type: str = "UNKNOWN"           # NDA | SLA | VENDOR | PARTNERSHIP
    contract_type_confidence: str = "low"    # high | medium | low
    contract_type_method: str = ""           # keyword | llm

    # ── Clause structure ─────────────────────────────────────────
    clause_segments: list[dict] = field(default_factory=list)
    # Each dict: { id, heading, text, level, clause_type }

    # ── Metadata Extraction Agent (filled later) ─────────────────
    metadata_status: AgentStatus = AgentStatus.PENDING
    contract_metadata: dict = field(default_factory=dict)

    # ── Clause Comparison Agent (filled later) ───────────────────
    clause_status: AgentStatus = AgentStatus.PENDING
    clauses: list[dict] = field(default_factory=list)

    # ── Risk Classification Agent (filled later) ─────────────────
    risk_status: AgentStatus = AgentStatus.PENDING
    risk_register: list[dict] = field(default_factory=list)

    # ── Report Agent (filled later) ──────────────────────────────
    report_status: AgentStatus = AgentStatus.PENDING
    report_path: Optional[str] = None