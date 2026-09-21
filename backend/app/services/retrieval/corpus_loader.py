import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.schemas.legal_passage import LegalPassage

CORPUS_PATH = Path(__file__).resolve().parents[4] / "legal_corpus" / "metadata" / "corpus.json"
SCOPE_PATH = Path(__file__).resolve().parents[4] / "legal_corpus" / "metadata" / "scope.json"


def passage_key(passage: LegalPassage) -> str:
    return f"{passage.source}:{passage.section}"


@lru_cache
def load_corpus(corpus_path: Path = CORPUS_PATH) -> list[LegalPassage]:
    data = json.loads(corpus_path.read_text(encoding="utf-8"))
    return [LegalPassage(**p) for p in data["passages"]]


@lru_cache
def load_scope(scope_path: Path = SCOPE_PATH) -> dict[str, Any]:
    """The machine-readable "supported legal scope" declaration (spec
    section 4), used e.g. in the PDF report (Milestone 13)."""
    result: dict[str, Any] = json.loads(scope_path.read_text(encoding="utf-8"))
    return result
