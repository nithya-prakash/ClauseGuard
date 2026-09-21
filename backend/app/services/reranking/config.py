"""Reranking configuration (spec section 10: "Keep retrieval configurable")."""

# Small multilingual cross-encoder (12-layer MiniLM) trained on mMARCO,
# which includes German - appropriate for reranking German query/passage
# pairs without needing a large model.
RERANKER_MODEL_NAME = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

# How many RRF candidates to feed the cross-encoder (it scores each
# query/passage pair independently, so this is the real cost driver).
RERANK_CANDIDATE_POOL = 10
# How many reranked passages to keep as final evidence for downstream
# reasoning (Milestone 8/9).
RERANK_TOP_K = 5
