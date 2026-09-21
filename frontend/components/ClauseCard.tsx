"use client";

import type { ClauseAnalysis, RiskLevel } from "@/lib/types";

const RISK_STYLES: Record<RiskLevel, string> = {
  LOW: "bg-green-100 text-green-800 border-green-300",
  MEDIUM: "bg-amber-100 text-amber-800 border-amber-300",
  HIGH: "bg-red-100 text-red-800 border-red-300",
  INSUFFICIENT_EVIDENCE: "bg-slate-100 text-slate-600 border-slate-300",
};

function RiskBadge({ level }: { level: RiskLevel }) {
  return (
    <span className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold ${RISK_STYLES[level]}`}>
      {level.replace("_", " ")}
    </span>
  );
}

function ClassificationBadge({ label }: { label: string }) {
  return (
    <span className="rounded-full border border-blue-300 bg-blue-100 px-2.5 py-0.5 text-xs font-semibold text-blue-800">
      {label}
    </span>
  );
}

function NotConfiguredBadge() {
  return (
    <span className="rounded-full border border-slate-300 bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-600">
      LLM NOT CONFIGURED
    </span>
  );
}

export default function ClauseCard({ analysis }: { analysis: ClauseAnalysis }) {
  const { clause, classification, classification_error, reasoning, reasoning_error } = analysis;

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold text-slate-800">
          {clause.section ?? `Clause ${clause.position}`}
          {clause.heading && <span className="font-normal text-slate-500"> — {clause.heading}</span>}
        </h3>
        <div className="flex items-center gap-2">
          {classification ? (
            <ClassificationBadge label={classification.clause_type} />
          ) : (
            <span className="text-xs text-slate-400">
              classification unavailable{classification_error ? `: ${classification_error}` : ""}
            </span>
          )}
          {reasoning ? (
            <RiskBadge level={reasoning.risk_level} />
          ) : reasoning_error ? (
            <NotConfiguredBadge />
          ) : null}
        </div>
      </div>

      <p className="mb-4 whitespace-pre-wrap rounded-md bg-slate-50 p-3 text-sm text-slate-700">
        {clause.text}
      </p>

      {reasoning && reasoning.status === "INSUFFICIENT_EVIDENCE" && (
        <div className="rounded-md border border-slate-300 bg-slate-50 p-3 text-sm text-slate-600">
          <strong>Insufficient legal evidence.</strong> {reasoning.explanation}
        </div>
      )}

      {!reasoning && reasoning_error && (
        <div className="rounded-md border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800">
          <strong>Reasoning not available:</strong> {reasoning_error}
        </div>
      )}

      {reasoning && reasoning.status !== "INSUFFICIENT_EVIDENCE" && (
        <div className="space-y-3">
          <p className="text-sm text-slate-700">{reasoning.explanation}</p>
          {reasoning.findings.map((finding, i) => (
            <div key={i} className="rounded-md border border-slate-200 p-3">
              <div className="mb-2 flex items-center justify-between">
                <span className="rounded bg-purple-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-purple-700">
                  AI finding
                </span>
                <span
                  className={
                    finding.citation_status === "VERIFIED"
                      ? "rounded bg-green-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-green-700"
                      : "rounded bg-red-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-red-700"
                  }
                  title={finding.citation_reason ?? undefined}
                >
                  {finding.citation_status === "VERIFIED" ? "citation verified" : "citation unverified"}
                </span>
              </div>
              <p className="text-sm text-slate-800">{finding.claim}</p>
              <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                Legal source
              </p>
              <p className="text-sm text-slate-600">
                {finding.citation} — {finding.legal_basis}
              </p>
              <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                Evidence
              </p>
              <p className="text-sm italic text-slate-500">&ldquo;{finding.evidence}&rdquo;</p>
            </div>
          ))}
          {reasoning.limitations.length > 0 && (
            <ul className="list-disc pl-5 text-xs text-slate-400">
              {reasoning.limitations.map((l, i) => (
                <li key={i}>{l}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
