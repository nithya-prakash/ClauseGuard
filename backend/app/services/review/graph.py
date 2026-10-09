"""LangGraph review flow: triage -> human review (interrupt) -> finalize.

Takes a finished DocumentAnalysisResult and decides which clauses a human
must look at before the report is trusted: anything not cleanly LOW-risk,
without a verified citation, with low confidence, or with a pipeline error.
Flagged clauses pause the graph via `interrupt()`; the reviewer's decisions
resume it. The flow records the human decision next to the AI screening
signal; it never changes the AI risk level, and a flagged clause without a
decision is reported as UNREVIEWED rather than silently accepted.
Deterministic (no LLM calls).
"""
from typing import Any, Literal, TypedDict, cast

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import BaseModel

from app.schemas.pipeline import ClauseAnalysis, DocumentAnalysisResult

Decision = Literal["CONFIRM", "DISMISS", "ESCALATE"]


class ReviewedClause(BaseModel):
    clause_id: str
    risk_level: str | None
    review_reasons: list[str]
    review_status: Literal["AUTO_ACCEPTED", "UNREVIEWED", "CONFIRM", "DISMISS", "ESCALATE"]
    reviewer_note: str | None = None


class ReviewedAnalysis(BaseModel):
    filename: str
    clauses: list[ReviewedClause]
    summary: dict[str, int]
    fully_reviewed: bool


class ReviewState(TypedDict, total=False):
    analysis: dict
    flagged: dict[str, list[str]]
    decisions: dict[str, dict]
    result: dict


def _risk(item: ClauseAnalysis) -> str | None:
    reasoning = item.reasoning
    return reasoning.risk_level if reasoning else None


def review_reasons(item: ClauseAnalysis) -> list[str]:
    reasons: list[str] = []
    r = item.reasoning
    if item.classification_error:
        reasons.append("classification_failed")
    if item.reasoning_error or r is None:
        reasons.append("no_reasoning_result")
        return reasons
    if r.risk_level in ("MEDIUM", "HIGH"):
        reasons.append(f"risk_{r.risk_level.lower()}")
    if r.risk_level == "INSUFFICIENT_EVIDENCE" or r.status == "INSUFFICIENT_EVIDENCE":
        reasons.append("insufficient_evidence")
    elif r.status == "REVIEW_RECOMMENDED":
        reasons.append("model_recommends_review")
    if any(f.citation_status != "VERIFIED" for f in r.findings):
        reasons.append("unverified_citation")
    if r.confidence == "LOW":
        reasons.append("low_confidence")
    return reasons


def build_review_graph(checkpointer=None):
    def triage(state: ReviewState) -> dict:
        analysis = DocumentAnalysisResult.model_validate(state["analysis"])
        flagged = {c.clause.clause_id: r for c in analysis.clauses if (r := review_reasons(c))}
        return {"flagged": flagged}

    def route(state: ReviewState) -> str:
        return "human_review" if state["flagged"] else "finalize"

    def human_review(state: ReviewState) -> dict:
        analysis = DocumentAnalysisResult.model_validate(state["analysis"])
        by_id = {c.clause.clause_id: c for c in analysis.clauses}
        decisions = interrupt(
            {
                "filename": analysis.filename,
                "to_review": [
                    {
                        "clause_id": cid,
                        "text": by_id[cid].clause.text[:400],
                        "risk_level": _risk(by_id[cid]),
                        "reasons": reasons,
                    }
                    for cid, reasons in state["flagged"].items()
                ],
                "allowed_decisions": ["CONFIRM", "DISMISS", "ESCALATE"],
            }
        )
        return {"decisions": decisions or {}}

    def finalize(state: ReviewState) -> dict:
        analysis = DocumentAnalysisResult.model_validate(state["analysis"])
        flagged, decisions = state["flagged"], state.get("decisions", {})
        clauses = []
        for item in analysis.clauses:
            cid = item.clause.clause_id
            risk = _risk(item)
            if cid not in flagged:
                status, note = "AUTO_ACCEPTED", None
            else:
                d = decisions.get(cid) or {}
                valid = d.get("decision") in ("CONFIRM", "DISMISS", "ESCALATE")
                status = d["decision"] if valid else "UNREVIEWED"
                note = d.get("note") if valid else None
            clauses.append(
                ReviewedClause(
                    clause_id=cid, risk_level=risk, review_reasons=flagged.get(cid, []),
                    review_status=cast(Any, status), reviewer_note=note,
                )
            )
        summary: dict[str, int] = {}
        for c in clauses:
            summary[c.review_status] = summary.get(c.review_status, 0) + 1
        result = ReviewedAnalysis(
            filename=analysis.filename, clauses=clauses, summary=summary,
            fully_reviewed=summary.get("UNREVIEWED", 0) == 0,
        )
        return {"result": result.model_dump()}

    g = StateGraph(ReviewState)
    g.add_node("triage", triage)
    g.add_node("human_review", human_review)
    g.add_node("finalize", finalize)
    g.add_edge(START, "triage")
    g.add_conditional_edges(
        "triage", route, {"human_review": "human_review", "finalize": "finalize"}
    )
    g.add_edge("human_review", "finalize")
    g.add_edge("finalize", END)
    return g.compile(checkpointer=checkpointer or MemorySaver())


def run_review(analysis: DocumentAnalysisResult, decisions: dict[str, dict]) -> ReviewedAnalysis:
    """Run the graph to completion for a stored analysis and the reviewer decisions so far.

    The graph is deterministic, so no checkpoint is persisted: it is replayed from the analysis,
    pausing at the interrupt and resuming with whatever decisions exist. Clauses without a
    decision stay UNREVIEWED."""
    from langgraph.types import Command

    graph = build_review_graph()
    cfg = {"configurable": {"thread_id": "review"}}
    out = graph.invoke({"analysis": analysis.model_dump()}, cfg)
    if "__interrupt__" in out:
        # An empty resume value is treated as "no resume", so pass a placeholder entry instead.
        out = graph.invoke(Command(resume=decisions or {"_none": {}}), cfg)
    return ReviewedAnalysis.model_validate(out["result"])
