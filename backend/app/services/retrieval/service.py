from qdrant_client import QdrantClient

from app.core.config import get_settings
from app.schemas.retrieval import RetrievedPassage
from app.services.retrieval import bm25, dense
from app.services.retrieval.config import BM25_TOP_K, DENSE_TOP_K, RRF_TOP_K
from app.services.retrieval.corpus_loader import load_corpus
from app.services.retrieval.rrf import index_passages_by_key, reciprocal_rank_fusion


def hybrid_search(
    client: QdrantClient,
    query: str,
    dense_top_k: int = DENSE_TOP_K,
    bm25_top_k: int = BM25_TOP_K,
    top_k: int = RRF_TOP_K,
) -> list[RetrievedPassage]:
    settings = get_settings()
    passages = load_corpus()

    dense_results = dense.search(client, settings.qdrant_collection, query, top_k=dense_top_k)
    bm25_index = bm25.build_index(passages)
    bm25_results = bm25.search(query, passages, bm25_index, top_k=bm25_top_k)

    fused = reciprocal_rank_fusion(
        [dense_results, bm25_results], index_passages_by_key(passages)
    )
    return fused[:top_k]
