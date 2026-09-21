"use client";

import { useEffect, useState } from "react";
import { ApiRequestError, getReportStatus } from "@/lib/api";

interface ReportScreenProps {
  documentId: string;
  onBack: () => void;
}

export default function ReportScreen({ documentId, onBack }: ReportScreenProps) {
  const [message, setMessage] = useState<string>("Checking report availability…");

  useEffect(() => {
    let cancelled = false;
    getReportStatus(documentId)
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiRequestError) {
          setMessage(err.message);
        } else {
          setMessage("Could not reach the report endpoint.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  return (
    <div className="mx-auto max-w-xl text-center">
      <h2 className="mb-4 text-xl font-semibold text-slate-800">PDF report</h2>
      <div className="rounded-md border border-slate-300 bg-slate-50 p-6 text-sm text-slate-600">
        {message}
      </div>
      <button
        onClick={onBack}
        className="mt-6 rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
      >
        Back to results
      </button>
    </div>
  );
}
