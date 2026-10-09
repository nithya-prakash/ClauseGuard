"""MCP server exposing ClauseGuard's legal corpus (read-only).

    python -m app.mcp_server        # stdio, run from backend/

Tools return real corpus passages with provenance (source, section, URL,
retrieval timestamp) and never generate legal text. Search is BM25 over the
corpus (no Qdrant / model download needed); cross-references are derived from
the passage text (see services/graph/references.py). Every response carries the
scope disclaimer: first-pass analysis support, not legal advice.
"""
from functools import lru_cache

from mcp.server.mcpserver import MCPServer

from app.services.graph.references import extract_edges
from app.services.retrieval import bm25
from app.services.retrieval.corpus_loader import load_corpus, load_scope, passage_key

mcp = MCPServer("clauseguard-legal-corpus")


@lru_cache
def _bm25():
    corpus = load_corpus()
    return corpus, bm25.build_index(corpus)


def _disclaimer() -> str:
    return load_scope()["disclaimer"]


def _passage(p, **extra) -> dict:
    return {
        "source": p.source, "section": p.section, "title": p.title, "text": p.text,
        "source_url": p.source_url, "retrieved_at": p.retrieved_at, **extra,
    }


@mcp.tool()
def get_scope() -> dict:
    """Which statutes/sections the corpus covers, what it does not, and the disclaimer."""
    return load_scope()


@mcp.tool()
def search_legal_corpus(query: str, top_k: int = 3) -> dict:
    """BM25 keyword search over the BGB/DSGVO passages; verbatim passages with provenance."""
    corpus, index = _bm25()
    hits = bm25.search(query, corpus, index, top_k=max(1, min(top_k, 10)))
    by_key = {passage_key(p): p for p in corpus}
    return {
        "disclaimer": _disclaimer(),
        "results": [
            _passage(by_key[f"{h.source}:{h.section}"], score=h.score, method="bm25") for h in hits
        ],
    }


@mcp.tool()
def get_passage(source: str, section: str) -> dict:
    """Fetch one passage, e.g. source='BGB', section='§ 307'. Error if not in the corpus."""
    for p in load_corpus():
        if p.source == source and p.section == section:
            return {"disclaimer": _disclaimer(), "passage": _passage(p)}
    return {
        "error": f"{source} {section} is not in the corpus (see get_scope).",
        "disclaimer": _disclaimer(),
    }


@mcp.tool()
def related_passages(source: str, section: str) -> dict:
    """Passages this one cites or is cited by (textual cross-references only)."""
    corpus = load_corpus()
    by_key = {passage_key(p): p for p in corpus}
    key = f"{source}:{section}"
    if key not in by_key:
        return {"error": f"{source} {section} is not in the corpus.", "disclaimer": _disclaimer()}
    edges = extract_edges(corpus)
    return {
        "disclaimer": _disclaimer(),
        "cites": [_passage(by_key[b]) for a, b in edges if a == key],
        "cited_by": [_passage(by_key[a]) for a, b in edges if b == key],
    }


if __name__ == "__main__":
    mcp.run()
