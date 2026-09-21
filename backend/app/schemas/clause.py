from pydantic import BaseModel


class Clause(BaseModel):
    clause_id: str
    text: str
    section: str | None
    heading: str | None = None
    page_start: int | None
    page_end: int | None
    position: int
    char_start: int
    char_end: int
