"use client";

import ClauseCard from "./ClauseCard";
import type { DocumentAnalysisResult } from "@/lib/types";

interface ResultsScreenProps {
  result: DocumentAnalysisResult;
  onViewReport: () => void;
  onReview?: () => void;
}

export default function ResultsScreen({ result, onViewReport, onReview }: ResultsScreenProps) {
  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-slate-800">{result.filename}</h2>
          <p className="text-sm text-slate-500">
            {result.clause_count} clauses · analyzed {new Date(result.analyzed_at).toLocaleString()}
          </p>
        </div>
        {onReview && (
          <button
            onClick={onReview}
            className="mr-2 rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Review flagged clauses
          </button>
        )}
        <button
          onClick={onViewReport}
          className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Generate report
        </button>
      </div>
      <div className="space-y-4">
        {result.clauses
          .slice()
          .sort((a, b) => a.clause.position - b.clause.position)
          .map((ca) => (
            <ClauseCard key={ca.clause.clause_id} analysis={ca} />
          ))}
      </div>
    </div>
  );
}
