from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.services.retrieval.config import (
    EMBEDDING_MODEL_NAME,
    EMBEDDING_PASSAGE_PREFIX,
    EMBEDDING_QUERY_PREFIX,
)


@lru_cache
def get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(EMBEDDING_MODEL_NAME)


def embed_query(text: str) -> list[float]:
    model = get_embedding_model()
    vector = model.encode(EMBEDDING_QUERY_PREFIX + text, normalize_embeddings=True)
    return vector.tolist()  # type: ignore[no-any-return]


def embed_passages(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    vectors = model.encode(
        [EMBEDDING_PASSAGE_PREFIX + t for t in texts], normalize_embeddings=True
    )
    return vectors.tolist()  # type: ignore[no-any-return]
