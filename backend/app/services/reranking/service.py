from qdrant_client import QdrantClient

from app.core.clients import get_neo4j_driver
from app.core.config import get_settings
from app.schemas.retrieval import RetrievedPassage
from app.services.graph.service import expand_with_graph
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
    cross-encoder rerank -> top-K evidence -> (optional) Neo4j cross-reference
    expansion."""
    candidates = hybrid_search(client, query, top_k=pool_size)
    top = rerank(query, candidates)[:top_k]
    if get_settings().graph_expansion_enabled:
        # After reranking, so graph-added passages never distort the rerank scores.
        top = expand_with_graph(get_neo4j_driver(), top)
    return top
