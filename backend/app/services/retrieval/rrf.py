"""Reciprocal Rank Fusion: combines multiple ranked lists into one, using
each item's RANK (position) in each list rather than its raw score - this is
what makes RRF work across rankers whose scores are on incompatible scales
(BM25's unbounded lexical scores vs. dense cosine similarity in [-1, 1])."""

from app.schemas.legal_passage import LegalPassage
from app.schemas.retrieval import RetrievedPassage
from app.services.retrieval.config import RRF_K
from app.services.retrieval.corpus_loader import passage_key


def reciprocal_rank_fusion(
    rankings: list[list[RetrievedPassage]], passages_by_key: dict[str, LegalPassage], k: int = RRF_K
) -> list[RetrievedPassage]:
    fused_scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            key = f"{item.source}:{item.section}"
            fused_scores[key] = fused_scores.get(key, 0.0) + 1.0 / (k + rank)

    ranked_keys = sorted(fused_scores.items(), key=lambda kv: kv[1], reverse=True)
    results = []
    for key, score in ranked_keys:
        passage = passages_by_key.get(key)
        if passage is None:
            continue
        results.append(
            RetrievedPassage(
                source=passage.source,
                section=passage.section,
                title=passage.title,
                text=passage.text,
                source_url=passage.source_url,
                score=round(score, 4),
                method="hybrid_rrf",
            )
        )
    return results


def index_passages_by_key(passages: list[LegalPassage]) -> dict[str, LegalPassage]:
    return {passage_key(p): p for p in passages}
