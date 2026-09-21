import re

from rank_bm25 import BM25Okapi

from app.schemas.legal_passage import LegalPassage
from app.schemas.retrieval import RetrievedPassage
from app.services.retrieval.config import BM25_TOP_K

_TOKEN_RE = re.compile(r"[a-zA-ZäöüÄÖÜß]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def build_index(passages: list[LegalPassage]) -> BM25Okapi:
    tokenized = [tokenize(p.text) for p in passages]
    return BM25Okapi(tokenized)


def search(
    query: str, passages: list[LegalPassage], index: BM25Okapi, top_k: int = BM25_TOP_K
) -> list[RetrievedPassage]:
    scores = index.get_scores(tokenize(query))
    ranked = sorted(zip(passages, scores, strict=True), key=lambda x: x[1], reverse=True)
    return [
        RetrievedPassage(
            source=p.source,
            section=p.section,
            title=p.title,
            text=p.text,
            source_url=p.source_url,
            score=round(float(score), 4),
            method="bm25",
        )
        for p, score in ranked[:top_k]
        if score > 0
    ]
