import pytest
from langgraph.types import Command

from app.schemas.clause import Clause
from app.schemas.pipeline import ClauseAnalysis, DocumentAnalysisResult
from app.schemas.reasoning import ReasoningResult, VerifiedFinding
from app.services.review.graph import build_review_graph

pytestmark = pytest.mark.asyncio


def _clause(cid):
    return Clause(clause_id=cid, text=f"text {cid}", section=None, page_start=1, page_end=1,
                  position=0, char_start=0, char_end=5)


def _finding(status="VERIFIED"):
    return VerifiedFinding(claim="c", legal_basis="b", citation="[BGB § 307]", evidence="e",
                           citation_status=status, citation_reason=None)


def _reasoning(cid, risk="LOW", status="OK", conf="HIGH", findings=None):
    return ReasoningResult(clause_id=cid, classification="X", risk_level=risk, status=status,
                           findings=findings if findings is not None else [_finding()],
                           explanation="e", confidence=conf, limitations=[])


def _analysis(*items):
    return DocumentAnalysisResult(filename="c.pdf", analyzed_at="now", clause_count=len(items),
                                  clauses=list(items)).model_dump()


def _item(cid, reasoning=None, error=None):
    return ClauseAnalysis(clause=_clause(cid), classification=None, classification_error=None,
                          reasoning=reasoning, reasoning_error=error)


async def test_clean_document_skips_human_review():
    graph = build_review_graph()
    cfg = {"configurable": {"thread_id": "a"}}
    out = await graph.ainvoke({"analysis": _analysis(_item("c1", _reasoning("c1")))}, cfg)
    assert "__interrupt__" not in out
    assert out["result"]["summary"] == {"AUTO_ACCEPTED": 1} and out["result"]["fully_reviewed"]


async def test_flagged_clauses_pause_then_resume_with_decisions():
    items = [
        _item("ok", _reasoning("ok")),
        _item("hi", _reasoning("hi", risk="HIGH", status="REVIEW_RECOMMENDED")),
        _item("cit", _reasoning("cit", findings=[_finding("CITATION_UNVERIFIED")])),
        _item("err", None, error="llm not configured"),
    ]
    graph = build_review_graph()
    cfg = {"configurable": {"thread_id": "b"}}
    paused = await graph.ainvoke({"analysis": _analysis(*items)}, cfg)
    flagged = {c["clause_id"]: c["reasons"] for c in paused["__interrupt__"][0].value["to_review"]}
    assert set(flagged) == {"hi", "cit", "err"}
    assert "risk_high" in flagged["hi"] and "unverified_citation" in flagged["cit"]

    done = await graph.ainvoke(
        Command(
            resume={"hi": {"decision": "CONFIRM", "note": "agree"}, "cit": {"decision": "bogus"}}
        ),
        cfg
    )
    by_id = {c["clause_id"]: c for c in done["result"]["clauses"]}
    assert by_id["ok"]["review_status"] == "AUTO_ACCEPTED"
    assert by_id["hi"]["review_status"] == "CONFIRM" and by_id["hi"]["reviewer_note"] == "agree"
    assert by_id["cit"]["review_status"] == "UNREVIEWED"  # invalid decision is not accepted
    assert by_id["err"]["review_status"] == "UNREVIEWED"
    assert by_id["hi"]["risk_level"] == "HIGH"  # AI signal is preserved, never overwritten
    assert done["result"]["fully_reviewed"] is False
