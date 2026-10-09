"""Load the legal corpus into Neo4j:  python scripts/build_graph.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from neo4j import GraphDatabase  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.services.graph.references import extract_edges  # noqa: E402
from app.services.graph.store import GraphStore  # noqa: E402
from app.services.retrieval.corpus_loader import CORPUS_PATH, load_corpus  # noqa: E402

if __name__ == "__main__":
    s = get_settings()
    passages = load_corpus()
    edges = extract_edges(passages)
    version = json.loads(CORPUS_PATH.read_text())["corpus_version"]
    with GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password)) as driver:
        GraphStore(driver).upsert_corpus(passages, edges, version)
    print(f"Loaded {len(passages)} passages and {len(edges)} REFERENCES edges.")
