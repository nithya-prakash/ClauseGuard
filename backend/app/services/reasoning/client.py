from typing import Any

from anthropic import Anthropic

from app.core.exceptions import PipelineStageError
from app.schemas.retrieval import RetrievedPassage
from app.services.classification.labels import CLAUSE_LABELS
from app.services.reasoning.prompts import SYSTEM_PROMPT, build_user_prompt

TOOL_NAME = "submit_risk_assessment"

TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": "Submit the structured first-pass risk assessment for this contract clause.",
    "input_schema": {
        "type": "object",
        "properties": {
            "clause_id": {"type": "string"},
            "classification": {"type": "string", "enum": CLAUSE_LABELS},
            "risk_level": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"]},
            "status": {"type": "string", "enum": ["OK", "REVIEW_RECOMMENDED"]},
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim": {"type": "string"},
                        "legal_basis": {"type": "string"},
                        "citation": {
                            "type": "string",
                            "description": "e.g. '§ 307 BGB' or 'Art. 28 DSGVO' - must "
                            "reference a passage actually given in the legal evidence.",
                        },
                        "evidence": {
                            "type": "string",
                            "description": "A direct quote or close paraphrase from the "
                            "cited legal evidence passage that supports the claim.",
                        },
                    },
                    "required": ["claim", "legal_basis", "citation", "evidence"],
                },
            },
            "explanation": {"type": "string"},
            "confidence": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"]},
            "limitations": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "clause_id",
            "classification",
            "risk_level",
            "status",
            "findings",
            "explanation",
            "confidence",
            "limitations",
        ],
    },
}


def call_llm(
    api_key: str,
    model: str,
    clause_id: str,
    clause_text: str,
    classification: str,
    evidence: list[RetrievedPassage],
) -> dict[str, Any]:
    client = Anthropic(api_key=api_key)
    user_prompt = build_user_prompt(clause_id, clause_text, classification, evidence)

    # TOOL_SCHEMA/tool_choice are plain dicts (not the SDK's precise
    # TypedDicts) so this call's exact overload can't be statically matched;
    # the shapes are correct at runtime per the Anthropic API reference.
    response = client.messages.create(  # type: ignore[call-overload]
        model=model,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        tools=[TOOL_SCHEMA],
        tool_choice={"type": "tool", "name": TOOL_NAME},
        messages=[{"role": "user", "content": user_prompt}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == TOOL_NAME:
            result: dict[str, Any] = block.input  # type: ignore[assignment]
            return result

    raise PipelineStageError("reasoning", "LLM response did not include the expected tool call.")
