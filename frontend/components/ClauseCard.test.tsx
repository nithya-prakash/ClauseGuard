import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ClauseCard from "./ClauseCard";
import type { ClauseAnalysis } from "@/lib/types";

const baseClause = {
  clause_id: "c1",
  text: "Der Auftragnehmer haftet nur für Vorsatz und grobe Fahrlässigkeit.",
  section: "§ 4",
  heading: "Haftung",
  page_start: 1,
  page_end: 1,
  position: 4,
};

describe("ClauseCard", () => {
  it("shows the insufficient-evidence state, not a risk badge, when the gate declined to reason", () => {
    const analysis: ClauseAnalysis = {
      clause: baseClause,
      classification: { clause_type: "NON_COMPETE", confidence: 0.7, model_name: "lora" },
      classification_error: null,
      reasoning: {
        clause_id: "c1",
        classification: "NON_COMPETE",
        risk_level: "INSUFFICIENT_EVIDENCE",
        status: "INSUFFICIENT_EVIDENCE",
        findings: [],
        explanation: "No sufficiently relevant legal evidence was found for this clause.",
        confidence: "LOW",
        limitations: ["Not a statement that the clause is compliant or non-compliant."],
      },
      reasoning_error: null,
    };
    render(<ClauseCard analysis={analysis} />);

    expect(screen.getByText("INSUFFICIENT EVIDENCE")).toBeInTheDocument();
    expect(screen.getByText(/No sufficiently relevant legal evidence/)).toBeInTheDocument();
    expect(screen.queryByText("AI finding")).not.toBeInTheDocument();
  });

  it("shows a 'reasoning not available' state when no LLM is configured, not a fake risk level", () => {
    const analysis: ClauseAnalysis = {
      clause: baseClause,
      classification: { clause_type: "LIABILITY", confidence: 0.9, model_name: "lora" },
      classification_error: null,
      reasoning: null,
      reasoning_error:
        "Set LLM_PROVIDER=anthropic and ANTHROPIC_API_KEY to enable the reasoning stage.",
    };
    render(<ClauseCard analysis={analysis} />);

    expect(screen.getByText("LLM NOT CONFIGURED")).toBeInTheDocument();
    expect(screen.getByText(/Reasoning not available/)).toBeInTheDocument();
    expect(screen.queryByText(/^LOW$|^MEDIUM$|^HIGH$/)).not.toBeInTheDocument();
  });

  it("renders a real finding with a VERIFIED citation badge, claim, legal source, and evidence", () => {
    const analysis: ClauseAnalysis = {
      clause: baseClause,
      classification: { clause_type: "LIABILITY", confidence: 0.9, model_name: "lora" },
      classification_error: null,
      reasoning: {
        clause_id: "c1",
        classification: "LIABILITY",
        risk_level: "LOW",
        status: "OK",
        findings: [
          {
            claim: "The liability limitation is consistent with § 276 BGB.",
            legal_basis: "§ 276 BGB regelt die Verantwortlichkeit des Schuldners.",
            citation: "§ 276 BGB",
            evidence: "Der Schuldner hat Vorsatz und Fahrlässigkeit zu vertreten",
            citation_status: "VERIFIED",
            citation_reason: null,
          },
        ],
        explanation: "Standard liability limitation clause.",
        confidence: "HIGH",
        limitations: [],
      },
      reasoning_error: null,
    };
    render(<ClauseCard analysis={analysis} />);

    expect(screen.getByText("LOW")).toBeInTheDocument();
    expect(screen.getByText("AI finding")).toBeInTheDocument();
    expect(screen.getByText("citation verified")).toBeInTheDocument();
    expect(screen.getByText(/The liability limitation is consistent/)).toBeInTheDocument();
    expect(screen.getByText(/§ 276 BGB — § 276 BGB regelt/)).toBeInTheDocument();
  });

  it("renders a CITATION_UNVERIFIED badge distinctly from a verified one", () => {
    const analysis: ClauseAnalysis = {
      clause: baseClause,
      classification: { clause_type: "LIABILITY", confidence: 0.9, model_name: "lora" },
      classification_error: null,
      reasoning: {
        clause_id: "c1",
        classification: "LIABILITY",
        risk_level: "HIGH",
        status: "REVIEW_RECOMMENDED",
        findings: [
          {
            claim: "irrelevant",
            legal_basis: "irrelevant",
            citation: "§ 999 BGB",
            evidence: "irrelevant",
            citation_status: "CITATION_UNVERIFIED",
            citation_reason: "§ 999 BGB is not a known passage in the legal corpus.",
          },
        ],
        explanation: "x",
        confidence: "LOW",
        limitations: [],
      },
      reasoning_error: null,
    };
    render(<ClauseCard analysis={analysis} />);

    const badge = screen.getByText("citation unverified");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveAttribute("title", "§ 999 BGB is not a known passage in the legal corpus.");
    expect(screen.queryByText("citation verified")).not.toBeInTheDocument();
  });

  it("shows a classification-unavailable message when classification failed, not a blank badge", () => {
    const analysis: ClauseAnalysis = {
      clause: baseClause,
      classification: null,
      classification_error: "No trained classifier is available in this environment.",
      reasoning: null,
      reasoning_error: null,
    };
    render(<ClauseCard analysis={analysis} />);
    expect(screen.getByText(/classification unavailable/)).toBeInTheDocument();
  });
});
