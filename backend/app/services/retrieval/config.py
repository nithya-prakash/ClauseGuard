"""Retrieval configuration, kept in one place so it's easy to tune (spec
section 10: "Keep retrieval configurable")."""

EMBEDDING_MODEL_NAME = "intfloat/multilingual-e5-small"
# e5 models require this prefix convention on queries vs. passages, per the
# model card - it is not optional/cosmetic, dropping it measurably hurts
# retrieval quality for this model family.
EMBEDDING_QUERY_PREFIX = "query: "
EMBEDDING_PASSAGE_PREFIX = "passage: "

DENSE_TOP_K = 10
BM25_TOP_K = 10
RRF_TOP_K = 5
# Standard RRF damping constant (Cormack et al. 2009 use 60).
RRF_K = 60
