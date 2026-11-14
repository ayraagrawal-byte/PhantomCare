from enum import StrEnum

from pydantic import AwareDatetime, Field

from api.contracts.base import ContractModel
from api.contracts.evidence import EvidenceRecord
from api.contracts.indicators import ReviewPriorityScore


class CaseFinding(ContractModel):
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=2000)
    strength: float = Field(ge=0, le=1)
    evidence: tuple[EvidenceRecord, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = ()


class CaseFile(ContractModel):
    case_id: str = Field(min_length=1, max_length=100)
    target_id: str = Field(min_length=1, max_length=100)
    created_at: AwareDatetime
    score: ReviewPriorityScore
    findings: tuple[CaseFinding, ...]
    disclaimer: str = Field(
        default="These are indicators worth reviewing, not conclusions of fraud.",
        min_length=1,
        max_length=500,
    )


class TraceEventType(StrEnum):
    STARTED = "started"
    TOOL_CALLED = "tool_called"
    TOOL_COMPLETED = "tool_completed"
    EARLY_STOPPED = "early_stopped"
    SKEPTIC_REVIEW = "skeptic_review"
    CASE_WRITTEN = "case_written"
    FAILED = "failed"


class TraceEvent(ContractModel):
    event_id: str = Field(min_length=1, max_length=100)
    case_id: str = Field(min_length=1, max_length=100)
    occurred_at: AwareDatetime
    event_type: TraceEventType
    message: str = Field(min_length=1, max_length=1000)
    evidence: tuple[EvidenceRecord, ...] = ()

