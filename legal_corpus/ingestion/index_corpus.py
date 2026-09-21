"""Embed and index the legal corpus into Qdrant for dense retrieval.

Requires Qdrant running (docker compose up qdrant) and the corpus already
built (legal_corpus/metadata/corpus.json - run build_corpus.py first).

Usage:
    python legal_corpus/ingestion/index_corpus.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from qdrant_client import QdrantClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.services.retrieval.corpus_loader import load_corpus  # noqa: E402
from app.services.retrieval.dense import index_passages  # noqa: E402


def main() -> None:
    settings = get_settings()
    client = QdrantClient(url=settings.qdrant_url)
    passages = load_corpus()
    count = index_passages(client, settings.qdrant_collection, passages)
    print(f"Indexed {count} passages into Qdrant collection '{settings.qdrant_collection}'")


if __name__ == "__main__":
    main()
