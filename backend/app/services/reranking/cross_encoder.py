from functools import lru_cache

from sentence_transformers import CrossEncoder

from app.schemas.retrieval import RetrievedPassage
from app.services.reranking.config import RERANKER_MODEL_NAME


@lru_cache
def get_reranker() -> CrossEncoder:
    return CrossEncoder(RERANKER_MODEL_NAME)


def rerank(query: str, candidates: list[RetrievedPassage]) -> list[RetrievedPassage]:
    """Score every (query, candidate) pair with the cross-encoder and return
    candidates re-sorted by that score, highest first. Does not truncate -
    callers slice to their own top-K (see RERANK_TOP_K)."""
    if not candidates:
        return []

    model = get_reranker()
    pairs = [(query, c.text) for c in candidates]
    scores = model.predict(pairs)

    reranked = sorted(zip(candidates, scores, strict=True), key=lambda x: x[1], reverse=True)
    return [
        RetrievedPassage(
            source=c.source,
            section=c.section,
            title=c.title,
            text=c.text,
            source_url=c.source_url,
            score=round(float(score), 4),
            method="hybrid_rrf_reranked",
        )
        for c, score in reranked
    ]
