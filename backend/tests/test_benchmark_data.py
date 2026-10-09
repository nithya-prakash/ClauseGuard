import json
from pathlib import Path

from app.services.classification.labels import CLAUSE_LABELS

CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "data" / "benchmark" / "contracts"
CONTRACTS = json.loads((CONTRACTS_DIR / "contracts_source.json").read_text(encoding="utf-8"))[
    "contracts"
]


def test_benchmark_size():
    assert len(CONTRACTS) == 4
    assert sum(len(c["clauses"]) for c in CONTRACTS) >= 50


def test_labels_and_sections_are_well_formed():
    for contract in CONTRACTS:
        assert (CONTRACTS_DIR / f"{contract['id']}.pdf").exists()
        sections = [c["section"] for c in contract["clauses"]]
        assert sections == [f"§ {i}" for i in range(1, len(sections) + 1)]
        for clause in contract["clauses"]:
            assert clause["clause_type"] in CLAUSE_LABELS
            assert isinstance(clause["corpus_covered"], bool)
            assert clause["body"].strip() and clause["coverage_note"].strip()


def test_every_clause_type_is_represented_and_no_duplicate_text():
    clauses = [c for contract in CONTRACTS for c in contract["clauses"]]
    assert {c["clause_type"] for c in clauses} == set(CLAUSE_LABELS)
    bodies = [c["body"] for c in clauses]
    assert len(bodies) == len(set(bodies))
