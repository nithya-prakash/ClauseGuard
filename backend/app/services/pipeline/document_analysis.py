"""End-to-end per-document pipeline (spec's architecture diagram, Milestone
10): ingest -> normalize -> segment -> [per clause: classify -> retrieve +
rerank -> evidence sufficiency -> LLM reasoning -> citation verification].

A clause-level failure (no trained classifier, no configured LLM, a
malformed LLM response) is recorded on that clause and does NOT abort the
rest of the document - one stage's failure should not discard progress
already made on every other clause. Document-level failures (unsupported
file type, unparseable structure) are not caught here and propagate, since
there is nothing left to salvage.

Requires the legal corpus already indexed into Qdrant
(legal_corpus/ingestion/index_corpus.py) - this function does not index it
itself, that's a separate ops concern.
"""

from datetime import UTC, datetime
from pathlib import Path

from qdrant_client import QdrantClient

from app.core.exceptions import ClassifierNotTrainedError, LLMNotConfiguredError, PipelineStageError
from app.core.logging import get_logger
from app.schemas.classification import ClassificationResult
from app.schemas.pipeline import ClauseAnalysis, DocumentAnalysisResult
from app.services.classification.service import classify_clause, classify_clause_lora
from app.services.ingestion.service import ingest_document
from app.services.reasoning.service import assess_clause
from app.services.segmentation.segmenter import segment_document

logger = get_logger(__name__)


def _classify(text: str) -> tuple[ClassificationResult | None, str | None]:
    """LoRA first (measured better, see reports/classification/comparison.md),
    falling back to the baseline classifier if no LoRA adapter is trained in
    this environment. Returns (None, reason) only if neither is available."""
    try:
        return classify_clause_lora(text), None
    except ClassifierNotTrainedError:
        logger.info("lora_classifier_unavailable_falling_back_to_baseline")

    try:
        return classify_clause(text), None
    except ClassifierNotTrainedError as exc:
        return None, str(exc)


def analyze_document(path: Path, qdrant_client: QdrantClient) -> DocumentAnalysisResult:
    document = ingest_document(path)
    clauses = segment_document(document)

    clause_analyses: list[ClauseAnalysis] = []
    for clause in clauses:
        classification, classification_error = _classify(clause.text)
        classification_label = classification.clause_type if classification else "OTHER"

        reasoning = None
        reasoning_error = None
        try:
            reasoning = assess_clause(
                qdrant_client, clause.clause_id, clause.text, classification_label
            )
        except (LLMNotConfiguredError, PipelineStageError) as exc:
            reasoning_error = str(exc)
            logger.warning("clause_reasoning_failed", clause_id=clause.clause_id, error=str(exc))

        clause_analyses.append(
            ClauseAnalysis(
                clause=clause,
                classification=classification,
                classification_error=classification_error,
                reasoning=reasoning,
                reasoning_error=reasoning_error,
            )
        )

    return DocumentAnalysisResult(
        filename=path.name,
        analyzed_at=datetime.now(UTC).isoformat(),
        clause_count=len(clauses),
        clauses=clause_analyses,
    )
