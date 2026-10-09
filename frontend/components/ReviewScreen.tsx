"use client";

import { useEffect, useState } from "react";
import { ApiRequestError, getReview, submitReview } from "@/lib/api";
import type { ReviewDecision, ReviewedAnalysis } from "@/lib/types";

interface ReviewScreenProps {
  documentId: string;
  onBack: () => void;
}

const DECISIONS: ReviewDecision[] = ["CONFIRM", "DISMISS", "ESCALATE"];

export default function ReviewScreen({ documentId, onBack }: ReviewScreenProps) {
  const [review, setReview] = useState<ReviewedAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getReview(documentId)
      .then(setReview)
      .catch((err) => setError(err instanceof ApiRequestError ? err.message : "Could not load the review."));
  }, [documentId]);

  async function decide(clauseId: string, decision: ReviewDecision, note: string) {
    setSaving(true);
    setError(null);
    try {
      setReview(await submitReview(documentId, { [clauseId]: { decision, note: note || undefined } }));
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Could not save the decision.");
    } finally {
      setSaving(false);
    }
  }

  if (!review) {
    return <p className="text-sm text-slate-500">{error ?? "Loading review…"}</p>;
  }
  const flagged = review.clauses.filter((c) => c.review_status !== "AUTO_ACCEPTED");

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-slate-800">Human review</h2>
          <p className="text-sm text-slate-500">
            {flagged.length} of {review.clauses.length} clauses flagged ·{" "}
            {review.fully_reviewed ? "all reviewed" : "decisions pending"}. Decisions never change the AI risk level.
          </p>
        </div>
        <button onClick={onBack} className="text-sm text-slate-500 hover:text-slate-700">
          ← Back to results
        </button>
      </div>
      {error && <p role="alert" className="mb-3 text-sm text-red-700">{error}</p>}
      <ul className="space-y-3">
        {flagged.map((c) => (
          <ReviewRow key={c.clause_id} clause={c} disabled={saving} onDecide={decide} />
        ))}
      </ul>
    </div>
  );
}

function ReviewRow({
  clause,
  disabled,
  onDecide,
}: {
  clause: ReviewedAnalysis["clauses"][number];
  disabled: boolean;
  onDecide: (id: string, decision: ReviewDecision, note: string) => void;
}) {
  const [note, setNote] = useState(clause.reviewer_note ?? "");
  return (
    <li className="rounded-md border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <span className="font-medium text-slate-800">{clause.clause_id}</span>
        <span className="text-xs text-slate-500">
          AI risk: {clause.risk_level ?? "none"} · status: {clause.review_status}
        </span>
      </div>
      <p className="mt-1 text-sm text-slate-600">Flagged: {clause.review_reasons.join(", ")}</p>
      <input
        aria-label={`Note for ${clause.clause_id}`}
        value={note}
        maxLength={500}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Optional note"
        className="mt-2 w-full rounded border border-slate-300 px-2 py-1 text-sm"
      />
      <div className="mt-2 flex gap-2">
        {DECISIONS.map((d) => (
          <button
            key={d}
            disabled={disabled}
            onClick={() => onDecide(clause.clause_id, d, note)}
            className={`rounded border px-3 py-1 text-xs font-medium ${
              clause.review_status === d
                ? "border-slate-800 bg-slate-800 text-white"
                : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
            }`}
          >
            {d}
          </button>
        ))}
      </div>
    </li>
  );
}
