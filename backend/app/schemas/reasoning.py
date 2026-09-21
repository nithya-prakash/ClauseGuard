"""Structured LLM reasoning output (spec section 13-14)."""

from typing import Literal

from pydantic import BaseModel

from app.schemas.verification import CitationStatus

# Risk levels are a fixed, documented set - the model may not invent others.
# INSUFFICIENT_EVIDENCE is set by the system (evidence_sufficiency.py) BEFORE
# the LLM is ever called; the model itself only ever emits LOW/MEDIUM/HIGH.
#
# Criteria (also given to the model verbatim in the system prompt):
#   LOW    - clause is consistent with the retrieved legal provisions; no
#            significant issue found.
#   MEDIUM - clause raises a plausible concern under the retrieved
#            provisions that a human should review, but is not clearly
#            unlawful.
#   HIGH   - clause appears to conflict with or be prohibited by the
#            retrieved legal provisions.
# These are an AI-generated screening signal, not a legal conclusion (spec
# section 14).
RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "INSUFFICIENT_EVIDENCE"]
ModelRiskLevel = Literal["LOW", "MEDIUM", "HIGH"]
ReasoningStatus = Literal["OK", "REVIEW_RECOMMENDED", "INSUFFICIENT_EVIDENCE"]
ModelReasoningStatus = Literal["OK", "REVIEW_RECOMMENDED"]
Confidence = Literal["LOW", "MEDIUM", "HIGH"]


class Finding(BaseModel):
    claim: str
    legal_basis: str
    citation: str
    evidence: str


class VerifiedFinding(Finding):
    citation_status: CitationStatus
    citation_reason: str | None


class RawReasoningOutput(BaseModel):
    """Exactly what the LLM is asked to return via tool-use - validated
    before anything downstream trusts it (spec: "Do not let the model
    produce arbitrary unstructured output. Use schema validation.")."""

    clause_id: str
    classification: str
    risk_level: ModelRiskLevel
    status: ModelReasoningStatus
    findings: list[Finding]
    explanation: str
    confidence: Confidence
    limitations: list[str]


class ReasoningResult(BaseModel):
    """Final result returned to callers: either the INSUFFICIENT_EVIDENCE
    short-circuit (no LLM call made) or the LLM's output with each finding's
    citation verified (Milestone 8) against the actual retrieved evidence."""

    clause_id: str
    classification: str
    risk_level: RiskLevel
    status: ReasoningStatus
    findings: list[VerifiedFinding]
    explanation: str
    confidence: Confidence
    limitations: list[str]
