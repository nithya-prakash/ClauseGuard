"""Minimal schema for an LLM finding, needed by citation verification
(Milestone 8) ahead of full structured reasoning (Milestone 9), which will
extend this with classification/risk_level/status/explanation/confidence
per spec section 13's example JSON."""

from pydantic import BaseModel


class Finding(BaseModel):
    claim: str
    legal_basis: str
    citation: str
    evidence: str
