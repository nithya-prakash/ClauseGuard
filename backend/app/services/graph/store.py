"""Neo4j persistence and traversal. Takes a driver so it can be faked in tests."""
from typing import Any

from app.schemas.legal_passage import LegalPassage

UPSERT_PASSAGE = """
MERGE (p:Passage {key: $key})
SET p.source = $source, p.section = $section, p.title = $title,
    p.source_url = $source_url, p.corpus_version = $corpus_version
"""
UPSERT_EDGE = """
MATCH (a:Passage {key: $from_key}), (b:Passage {key: $to_key})
MERGE (a)-[:REFERENCES]->(b)
"""
# Passages connected to the seeds by a REFERENCES edge in either direction.
NEIGHBOURS = """
MATCH (s:Passage) WHERE s.key IN $keys
MATCH (s)-[:REFERENCES]-(n:Passage) WHERE NOT n.key IN $keys
RETURN DISTINCT n.key AS key, count(DISTINCT s) AS linked_seeds
ORDER BY linked_seeds DESC, key
LIMIT $limit
"""


class GraphStore:
    def __init__(self, driver: Any, database: str | None = None) -> None:
        self._driver = driver
        self._database = database

    def upsert_corpus(
        self, passages: list[LegalPassage], edges: list[tuple[str, str]], corpus_version: str
    ) -> None:
        with self._driver.session(database=self._database) as session:
            for p in passages:
                session.run(
                    UPSERT_PASSAGE,
                    key=f"{p.source}:{p.section}", source=p.source, section=p.section,
                    title=p.title, source_url=p.source_url, corpus_version=corpus_version,
                )
            for from_key, to_key in edges:
                session.run(UPSERT_EDGE, from_key=from_key, to_key=to_key)

    def neighbours(self, keys: list[str], limit: int) -> list[str]:
        with self._driver.session(database=self._database) as session:
            result = session.run(NEIGHBOURS, keys=keys, limit=limit)
            return [record["key"] for record in result]
