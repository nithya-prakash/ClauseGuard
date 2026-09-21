import json
from functools import lru_cache
from pathlib import Path

from app.schemas.legal_passage import LegalPassage

CORPUS_PATH = Path(__file__).resolve().parents[4] / "legal_corpus" / "metadata" / "corpus.json"


def passage_key(passage: LegalPassage) -> str:
    return f"{passage.source}:{passage.section}"


@lru_cache
def load_corpus(corpus_path: Path = CORPUS_PATH) -> list[LegalPassage]:
    data = json.loads(corpus_path.read_text(encoding="utf-8"))
    return [LegalPassage(**p) for p in data["passages"]]
