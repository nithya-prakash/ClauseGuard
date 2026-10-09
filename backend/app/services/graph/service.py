import logging
from typing import Any

from app.schemas.retrieval import RetrievedPassage
from app.services.graph.store import GraphStore
from app.services.retrieval.corpus_loader import load_corpus, passage_key

logger = logging.getLogger(__name__)

NEIGHBOUR_SCORE_FACTOR = 0.5  # graph-added passages rank below the seed they came from


def expand_with_graph(
    driver: Any, seeds: list[RetrievedPassage], max_added: int = 3
) -> list[RetrievedPassage]:
    """Appends passages cited by / citing the retrieved ones. Text and URL come
    from the real corpus entry, so provenance is unchanged. Fails open: any
    graph error returns the seeds untouched."""
    if not seeds:
        return seeds
    seed_keys = [f"{s.source}:{s.section}" for s in seeds]
    try:
        neighbour_keys = GraphStore(driver).neighbours(seed_keys, max_added)
    except Exception:  # noqa: BLE001 - graph is an optional enhancement
        logger.warning("graph expansion failed; returning un-expanded results", exc_info=True)
        return seeds
    corpus = {passage_key(p): p for p in load_corpus()}
    floor = min(s.score for s in seeds) * NEIGHBOUR_SCORE_FACTOR
    added = [
        RetrievedPassage(
            source=p.source, section=p.section, title=p.title, text=p.text,
            source_url=p.source_url, score=floor, method="graph_expanded",
        )
        for k in neighbour_keys
        if (p := corpus.get(k)) is not None
    ]
    return [*seeds, *added]
