import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ProcessingScreen from "./ProcessingScreen";
import type { DocumentAnalysisResult } from "@/lib/types";

function makeResult(overrides: Partial<DocumentAnalysisResult> = {}): DocumentAnalysisResult {
  return {
    filename: "contract.pdf",
    analyzed_at: "2026-09-20T12:00:00Z",
    clause_count: 1,
    clauses: [
      {
        clause: {
          clause_id: "c1",
          text: "Der Verkäufer haftet nur für Vorsatz und grobe Fahrlässigkeit.",
          section: "§ 4",
          heading: "Haftung",
          page_start: 1,
          page_end: 1,
          position: 1,
        },
        classification: { clause_type: "LIABILITY", confidence: 0.9, model_name: "lora" },
        classification_error: null,
        reasoning: null,
        reasoning_error:
          "Set LLM_PROVIDER=anthropic and ANTHROPIC_API_KEY to enable the reasoning stage.",
      },
    ],
    ...overrides,
  };
}

describe("ProcessingScreen", () => {
  it("shows a loading state while isLoading is true, with no continue button", () => {
    render(<ProcessingScreen isLoading={true} result={null} onContinue={vi.fn()} />);
    expect(screen.getByText(/Analyzing document/)).toBeInTheDocument();
    expect(screen.queryByText("View results")).not.toBeInTheDocument();
  });

  it("marks classification done but risk analysis not-done when no clause reached a real LLM call", () => {
    render(<ProcessingScreen isLoading={false} result={makeResult()} onContinue={vi.fn()} />);
    expect(screen.getByText("Clauses classified")).toBeInTheDocument();
    expect(
      screen.getByText(/No clause reached a real LLM risk assessment/)
    ).toBeInTheDocument();
  });

  it("marks risk analysis and citation verification done when a real reasoning result with findings exists", () => {
    const result = makeResult({
      clauses: [
        {
          clause: {
            clause_id: "c1",
            text: "x",
            section: "§ 4",
            heading: null,
            page_start: 1,
            page_end: 1,
            position: 1,
          },
          classification: { clause_type: "LIABILITY", confidence: 0.9, model_name: "lora" },
          classification_error: null,
          reasoning: {
            clause_id: "c1",
            classification: "LIABILITY",
            risk_level: "LOW",
            status: "OK",
            findings: [
              {
                claim: "x",
                legal_basis: "§ 276 BGB",
                citation: "§ 276 BGB",
                evidence: "x",
                citation_status: "VERIFIED",
                citation_reason: null,
              },
            ],
            explanation: "x",
            confidence: "HIGH",
            limitations: [],
          },
          reasoning_error: null,
        },
      ],
    });
    render(<ProcessingScreen isLoading={false} result={result} onContinue={vi.fn()} />);
    expect(
      screen.queryByText(/No clause reached a real LLM risk assessment/)
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/No LLM findings existed/)).not.toBeInTheDocument();
  });

  it("calls onContinue when 'View results' is clicked", () => {
    const onContinue = vi.fn();
    render(<ProcessingScreen isLoading={false} result={makeResult()} onContinue={onContinue} />);
    fireEvent.click(screen.getByText("View results"));
    expect(onContinue).toHaveBeenCalledTimes(1);
  });
});
