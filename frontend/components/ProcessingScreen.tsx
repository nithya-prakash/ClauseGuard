"use client";

import type { DocumentAnalysisResult } from "@/lib/types";

interface ProcessingScreenProps {
  isLoading: boolean;
  result: DocumentAnalysisResult | null;
  onContinue: () => void;
}

interface Stage {
  label: string;
  done: boolean;
  note?: string;
}

// Every checkmark below is computed from the REAL response - there is no
// live progress channel yet (analysis runs synchronously in one request;
// background job processing is Milestone 23), so this screen can only show
// "not started" -> "done", not incremental fake progress while waiting.
function computeStages(result: DocumentAnalysisResult): Stage[] {
  const hasClauses = result.clause_count > 0;
  const anyClassified = result.clauses.some((c) => c.classification !== null);
  const anyReasoningAttempted = result.clauses.some(
    (c) => c.reasoning !== null || c.reasoning_error !== null
  );
  const anyRealRiskAssessment = result.clauses.some(
    (c) => c.reasoning !== null && c.reasoning.status !== "INSUFFICIENT_EVIDENCE"
  );
  const anyCitationVerified = result.clauses.some(
    (c) => c.reasoning !== null && c.reasoning.findings.length > 0
  );

  return [
    { label: "Document parsed", done: true },
    { label: "Clauses detected", done: hasClauses },
    { label: "Clauses classified", done: anyClassified },
    { label: "Legal evidence retrieved", done: anyReasoningAttempted },
    {
      label: "Risk analysis completed",
      done: anyRealRiskAssessment,
      note: anyRealRiskAssessment
        ? undefined
        : "No clause reached a real LLM risk assessment - see per-clause reasoning status on the next screen.",
    },
    {
      label: "Citations verified",
      done: anyCitationVerified,
      note: anyCitationVerified ? undefined : "No LLM findings existed to verify citations against.",
    },
  ];
}

export default function ProcessingScreen({ isLoading, result, onContinue }: ProcessingScreenProps) {
  if (isLoading || !result) {
    return (
      <div className="mx-auto flex max-w-xl flex-col items-center py-16 text-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-300 border-t-blue-600" />
        <p className="mt-4 text-slate-600">
          Analyzing document — this can take a moment (retrieval + reranking + LLM reasoning
          per clause).
        </p>
      </div>
    );
  }

  const stages = computeStages(result);

  return (
    <div className="mx-auto max-w-xl">
      <h2 className="mb-4 text-xl font-semibold text-slate-800">Processing</h2>
      <ul className="space-y-2">
        {stages.map((stage) => (
          <li key={stage.label} className="rounded-md border border-slate-200 bg-white p-3">
            <div className="flex items-center gap-2">
              <span
                className={
                  stage.done
                    ? "flex h-5 w-5 items-center justify-center rounded-full bg-green-600 text-xs text-white"
                    : "flex h-5 w-5 items-center justify-center rounded-full bg-slate-300 text-xs text-white"
                }
              >
                {stage.done ? "✓" : "–"}
              </span>
              <span className="font-medium text-slate-700">{stage.label}</span>
            </div>
            {stage.note && <p className="mt-1 pl-7 text-xs text-slate-500">{stage.note}</p>}
          </li>
        ))}
      </ul>
      <button
        onClick={onContinue}
        className="mt-6 rounded-md bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700"
      >
        View results
      </button>
    </div>
  );
}
