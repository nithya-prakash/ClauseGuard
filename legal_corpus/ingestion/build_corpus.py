"""Build the full legal corpus by running both fetchers and writing the
combined, versioned, structured output to legal_corpus/metadata/corpus.json
(committed - this is the actual deliverable; the raw HTML snapshots under
legal_corpus/sources/ are gitignored and exist only for audit/reproducibility).

Also writes legal_corpus/metadata/scope.json, a small machine-readable
description of ClauseGuard's supported legal scope (spec section 4: "The
system must expose its supported legal scope") that the API can serve
directly once Milestone 10 wires the corpus into the pipeline.

Usage:
    python legal_corpus/ingestion/build_corpus.py
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from legal_corpus.ingestion.fetch_bgb import fetch_all as fetch_bgb  # noqa: E402
from legal_corpus.ingestion.fetch_dsgvo import fetch_all as fetch_dsgvo  # noqa: E402

METADATA_DIR = ROOT / "legal_corpus" / "metadata"
CORPUS_VERSION = "2026-09-20-v1"


def build() -> None:
    passages = fetch_bgb() + fetch_dsgvo()

    corpus = {
        "corpus_version": CORPUS_VERSION,
        "built_at": datetime.now(UTC).isoformat(),
        "provenance_note": (
            "All passages fetched programmatically from official sources "
            "(gesetze-im-internet.de for BGB, EUR-Lex CELEX:32016R0679 for "
            "DSGVO/GDPR) by legal_corpus/ingestion/fetch_bgb.py and "
            "fetch_dsgvo.py - not hand-typed, not scraped from unofficial "
            "sites. Re-run legal_corpus/ingestion/build_corpus.py to refresh."
        ),
        "passage_count": len(passages),
        "passages": [p.model_dump() for p in passages],
    }

    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    (METADATA_DIR / "corpus.json").write_text(
        json.dumps(corpus, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    scope = {
        "corpus_version": CORPUS_VERSION,
        "disclaimer": (
            "ClauseGuard performs AI-assisted first-pass compliance/risk "
            "analysis and does not constitute legal advice. It does not "
            "determine whether a contract is legally valid."
        ),
        "jurisdiction": "Germany (BGB) and European Union (DSGVO/GDPR, "
        "directly applicable in Germany)",
        "sources": sorted({p.source for p in passages}),
        "covered_sections": [
            {"source": p.source, "section": p.section, "title": p.title} for p in passages
        ],
        "not_covered": (
            "This is a deliberately constrained scope, not comprehensive "
            "German contract law: only the sections/articles listed above. "
            "Any clause outside this scope will be reported as "
            "INSUFFICIENT_EVIDENCE rather than reasoned about without a "
            "legal basis."
        ),
    }
    (METADATA_DIR / "scope.json").write_text(
        json.dumps(scope, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"Built corpus: {len(passages)} passages -> {METADATA_DIR / 'corpus.json'}")


if __name__ == "__main__":
    build()
