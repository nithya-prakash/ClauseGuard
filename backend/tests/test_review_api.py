from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.schemas.pipeline import DocumentAnalysisResult
from app.services.pipeline.store import DocumentRecord, save_document, save_result
from tests.test_review_graph import _finding, _item, _reasoning


def _seed(document_id: str = "doc1") -> str:
    record = DocumentRecord(document_id, "c.pdf", Path("/nonexistent/c.pdf"), "application/pdf")
    save_document(record)
    items = [
        _item("ok", _reasoning("ok")),
        _item("hi", _reasoning("hi", risk="HIGH", status="REVIEW_RECOMMENDED")),
        _item("cit", _reasoning("cit", findings=[_finding("CITATION_UNVERIFIED")])),
    ]
    save_result(
        document_id,
        DocumentAnalysisResult(
            filename="c.pdf", analyzed_at="now", clause_count=len(items), clauses=items
        ),
    )
    return document_id


def test_review_requires_existing_analyzed_document(client: TestClient):
    assert client.get("/documents/nope/review").status_code == 404
    save_document(DocumentRecord("raw", "c.pdf", Path("/x"), "application/pdf"))
    assert client.get("/documents/raw/review").status_code == 404


def test_get_review_lists_flagged_clauses_as_unreviewed(client: TestClient):
    body = client.get(f"/documents/{_seed()}/review").json()
    status = {c["clause_id"]: c["review_status"] for c in body["clauses"]}
    assert status == {"ok": "AUTO_ACCEPTED", "hi": "UNREVIEWED", "cit": "UNREVIEWED"}
    assert body["fully_reviewed"] is False


def test_decisions_persist_across_requests_and_never_change_ai_risk(client: TestClient):
    doc = _seed()
    escalate = {"hi": {"decision": "ESCALATE", "note": "x"}}
    r1 = client.put(f"/documents/{doc}/review", json={"decisions": escalate})
    assert r1.status_code == 200
    assert r1.json()["summary"] == {"AUTO_ACCEPTED": 1, "ESCALATE": 1, "UNREVIEWED": 1}

    dismiss = {"cit": {"decision": "DISMISS"}}
    r2 = client.put(f"/documents/{doc}/review", json={"decisions": dismiss})
    body = r2.json()
    assert body["fully_reviewed"] is True
    by_id = {c["clause_id"]: c for c in body["clauses"]}
    assert by_id["hi"]["review_status"] == "ESCALATE" and by_id["hi"]["reviewer_note"] == "x"
    assert by_id["hi"]["risk_level"] == "HIGH"

    assert client.get(f"/documents/{doc}/review").json() == body


@pytest.mark.parametrize(
    "payload",
    [
        {"decisions": {"ok": {"decision": "CONFIRM"}}},  # clause was not flagged
        {"decisions": {"missing": {"decision": "CONFIRM"}}},  # unknown clause
        {"decisions": {"hi": {"decision": "bogus"}}},  # invalid decision
        {"decisions": {"hi": {"decision": "CONFIRM", "note": "n" * 501}}},  # note too long
    ],
)
def test_invalid_decisions_are_rejected(client: TestClient, payload: dict):
    doc = _seed()
    assert client.put(f"/documents/{doc}/review", json=payload).status_code == 422
    assert client.get(f"/documents/{doc}/review").json()["fully_reviewed"] is False


def test_deleting_document_removes_its_review_decisions(client: TestClient):
    doc = _seed()
    client.put(f"/documents/{doc}/review", json={"decisions": {"hi": {"decision": "CONFIRM"}}})
    assert client.delete(f"/documents/{doc}").status_code == 204
    from app.services.review.store import get_decisions

    assert get_decisions(doc) == {}
