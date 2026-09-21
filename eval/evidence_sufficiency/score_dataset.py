"""Phase 2 (Milestone 16): runs the REAL retrieve_and_rerank pipeline against
the live Qdrant corpus for every example in
data/benchmark/evidence_sufficiency/dataset.json, and records the real top
cross-encoder score plus the full retrieved evidence. Nothing here is
simulated - every score is a live pipeline call, same as production.

Requires Qdrant running with the corpus indexed:
    docker compose up -d qdrant
    QDRANT_URL=http://localhost:6339 python legal_corpus/ingestion/index_corpus.py

Usage:
    QDRANT_URL=http://localhost:6339 python eval/evidence_sufficiency/score_dataset.py
"""

import json
import sys
from pathlib import Path

from qdrant_client import QdrantClient

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.services.reranking.service import retrieve_and_rerank  # noqa: E402

DATASET_PATH = ROOT / "data" / "benchmark" / "evidence_sufficiency" / "dataset.json"
OUTPUT_PATH = ROOT / "data" / "benchmark" / "evidence_sufficiency" / "scored_dataset.json"


def main() -> None:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    settings = get_settings()
    client = QdrantClient(url=settings.qdrant_url)

    scored = []
    for clause in dataset["clauses"]:
        passages = retrieve_and_rerank(client, clause["clause_text"])
        top_score = passages[0].score if passages else None
        scored.append(
            {
                **clause,
                "clause_length_chars": len(clause["clause_text"]),
                "top_score": top_score,
                "top_passage": (
                    {
                        "source": passages[0].source,
                        "section": passages[0].section,
                        "method": passages[0].method,
                    }
                    if passages
                    else None
                ),
                "retrieved_evidence": [
                    {"source": p.source, "section": p.section, "score": p.score} for p in passages
                ],
            }
        )

    output = {
        "_provenance": (
            "Real retrieve_and_rerank() output against the live Qdrant corpus "
            "(legal_corpus/metadata/corpus.json, 15 passages), captured for every "
            "example in dataset.json. Not simulated - regenerate by re-running this "
            "script against a running Qdrant with the corpus indexed."
        ),
        "clauses": scored,
    }
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    n_with_score = sum(1 for c in scored if c["top_score"] is not None)
    print(f"Scored {len(scored)} clauses ({n_with_score} with retrieved evidence).")
    print(f"Written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
