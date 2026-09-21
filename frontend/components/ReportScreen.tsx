"use client";

import { useEffect, useState } from "react";
import { ApiRequestError, downloadReport } from "@/lib/api";

interface ReportScreenProps {
  documentId: string;
  filename: string;
  onBack: () => void;
}

type Status = "loading" | "ready" | "error";

export default function ReportScreen({ documentId, filename, onBack }: ReportScreenProps) {
  const [status, setStatus] = useState<Status>("loading");
  const [message, setMessage] = useState<string>("Generating report…");

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;

    downloadReport(documentId)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = objectUrl;
        const base = filename.replace(/\.[^.]+$/, "");
        link.download = `${base}_clauseguard_report.pdf`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        setStatus("ready");
        setMessage("Report downloaded.");
      })
      .catch((err) => {
        if (cancelled) return;
        setStatus("error");
        setMessage(err instanceof ApiRequestError ? err.message : "Could not generate the report.");
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [documentId, filename]);

  return (
    <div className="mx-auto max-w-xl text-center">
      <h2 className="mb-4 text-xl font-semibold text-slate-800">PDF report</h2>
      <div
        className={`rounded-md border p-6 text-sm ${
          status === "error"
            ? "border-red-300 bg-red-50 text-red-700"
            : "border-slate-300 bg-slate-50 text-slate-600"
        }`}
      >
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
