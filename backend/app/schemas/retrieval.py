from typing import Literal

from pydantic import BaseModel

RetrievalMethod = Literal["dense", "bm25", "hybrid_rrf", "hybrid_rrf_reranked"]


class RetrievedPassage(BaseModel):
    source: str
    section: str
    title: str
    text: str
    source_url: str
    score: float
    method: RetrievalMethod
