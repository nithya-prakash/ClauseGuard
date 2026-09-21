from pydantic import BaseModel


class LegalPassage(BaseModel):
    source: str
    section: str
    title: str
    text: str
    jurisdiction: str
    domain: str
    source_url: str
    effective_date: str | None
    retrieved_at: str
