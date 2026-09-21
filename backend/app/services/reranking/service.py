from qdrant_client import QdrantClient

from app.schemas.retrieval import RetrievedPassage
from app.services.reranking.config import RERANK_CANDIDATE_POOL, RERANK_TOP_K
from app.services.reranking.cross_encoder import rerank
from app.services.retrieval.service import hybrid_search


def retrieve_and_rerank(
    client: QdrantClient,
    query: str,
    pool_size: int = RERANK_CANDIDATE_POOL,
    top_k: int = RERANK_TOP_K,
) -> list[RetrievedPassage]:
    """Full pipeline: dense + BM25 -> RRF -> top-N candidate pool ->
    cross-encoder rerank -> top-K evidence."""
    candidates = hybrid_search(client, query, top_k=pool_size)
    reranked = rerank(query, candidates)
    return reranked[:top_k]
