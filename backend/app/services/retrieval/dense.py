from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.schemas.legal_passage import LegalPassage
from app.schemas.retrieval import RetrievedPassage
from app.services.retrieval.config import DENSE_TOP_K
from app.services.retrieval.corpus_loader import passage_key
from app.services.retrieval.embeddings import embed_passages, embed_query


def ensure_collection(client: QdrantClient, collection_name: str, vector_size: int) -> None:
    existing = {c.name for c in client.get_collections().collections}
    if collection_name in existing:
        return
    client.create_collection(
        collection_name=collection_name,
        vectors_config=qmodels.VectorParams(size=vector_size, distance=qmodels.Distance.COSINE),
    )


def index_passages(client: QdrantClient, collection_name: str, passages: list[LegalPassage]) -> int:
    vectors = embed_passages([p.text for p in passages])
    ensure_collection(client, collection_name, vector_size=len(vectors[0]))

    points = [
        qmodels.PointStruct(
            id=i,
            vector=vector,
            payload={
                "key": passage_key(p),
                "source": p.source,
                "section": p.section,
                "title": p.title,
                "text": p.text,
                "source_url": p.source_url,
                "domain": p.domain,
                "jurisdiction": p.jurisdiction,
            },
        )
        for i, (p, vector) in enumerate(zip(passages, vectors, strict=True))
    ]
    client.upsert(collection_name=collection_name, points=points)
    return len(points)


def search(
    client: QdrantClient, collection_name: str, query: str, top_k: int = DENSE_TOP_K
) -> list[RetrievedPassage]:
    query_vector = embed_query(query)
    hits = client.query_points(
        collection_name=collection_name, query=query_vector, limit=top_k
    ).points
    return [
        RetrievedPassage(
            source=hit.payload["source"],  # type: ignore[index]
            section=hit.payload["section"],  # type: ignore[index]
            title=hit.payload["title"],  # type: ignore[index]
            text=hit.payload["text"],  # type: ignore[index]
            source_url=hit.payload["source_url"],  # type: ignore[index]
            score=round(float(hit.score), 4),
            method="dense",
        )
        for hit in hits
    ]
