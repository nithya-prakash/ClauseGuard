from pydantic import ValidationError
from qdrant_client import QdrantClient

from app.core.config import get_settings
from app.core.exceptions import LLMNotConfiguredError, PipelineStageError
from app.schemas.reasoning import RawReasoningOutput, ReasoningResult, VerifiedFinding
from app.services.reasoning.client import call_llm
from app.services.reranking.service import retrieve_and_rerank
from app.services.verification.citation import verify_citation
from app.services.verification.evidence_sufficiency import check_evidence_sufficiency


def assess_clause(
    client: QdrantClient, clause_id: str, clause_text: str, classification: str
) -> ReasoningResult:
    """Full per-clause pipeline: retrieve+rerank -> evidence sufficiency ->
    (if sufficient) LLM structured reasoning -> citation verification.

    Never calls the LLM when evidence is insufficient (cost + honesty: an
    LLM given no real evidence would have to either refuse or hallucinate a
    basis - the system decides this deterministically instead).
    """
    candidates = retrieve_and_rerank(client, clause_text)
    sufficiency = check_evidence_sufficiency(candidates)

    if sufficiency.status == "INSUFFICIENT_EVIDENCE":
        return ReasoningResult(
            clause_id=clause_id,
            classification=classification,
            risk_level="INSUFFICIENT_EVIDENCE",
            status="INSUFFICIENT_EVIDENCE",
            findings=[],
            explanation=sufficiency.reason or "Insufficient evidence.",
            confidence="LOW",
            limitations=[
                "No sufficiently relevant legal evidence was found in ClauseGuard's "
                "supported legal corpus for this clause. This is not a statement "
                "that the clause is compliant or non-compliant."
            ],
        )

    settings = get_settings()
    if not settings.llm_configured:
        raise LLMNotConfiguredError(
            "Set LLM_PROVIDER=anthropic and ANTHROPIC_API_KEY to enable the "
            "reasoning stage. Evidence sufficiency and retrieval work without it; "
            "this clause has sufficient evidence but no configured LLM to reason "
            "with it."
        )

    raw = call_llm(
        api_key=settings.anthropic_api_key,  # type: ignore[arg-type]
        model=settings.anthropic_model,
        clause_id=clause_id,
        clause_text=clause_text,
        classification=classification,
        evidence=sufficiency.evidence,
    )

    try:
        validated = RawReasoningOutput.model_validate(raw)
    except ValidationError as exc:
        raise PipelineStageError(
            "reasoning", f"LLM output failed schema validation: {exc}"
        ) from exc

    verified_findings = []
    for finding in validated.findings:
        check = verify_citation(finding, sufficiency.evidence)
        verified_findings.append(
            VerifiedFinding(
                **finding.model_dump(),
                citation_status=check.status,
                citation_reason=check.reason,
            )
        )

    return ReasoningResult(
        clause_id=validated.clause_id,
        classification=validated.classification,
        risk_level=validated.risk_level,
        status=validated.status,
        findings=verified_findings,
        explanation=validated.explanation,
        confidence=validated.confidence,
        limitations=validated.limitations,
    )
