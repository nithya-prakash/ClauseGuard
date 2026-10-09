"use client";

import { useState } from "react";
import Disclaimer from "@/components/Disclaimer";
import UploadScreen from "@/components/UploadScreen";
import ProcessingScreen from "@/components/ProcessingScreen";
import ResultsScreen from "@/components/ResultsScreen";
import ReportScreen from "@/components/ReportScreen";
import ReviewScreen from "@/components/ReviewScreen";
import { ApiRequestError, analyzeDocument, uploadDocument } from "@/lib/api";
import type { DocumentAnalysisResult } from "@/lib/types";

type Screen = "upload" | "processing" | "results" | "report" | "review";

export default function Home() {
  const [screen, setScreen] = useState<Screen>("upload");
  const [isLoading, setIsLoading] = useState(false);
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [result, setResult] = useState<DocumentAnalysisResult | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function handleFileSelected(file: File) {
    setErrorMessage(null);
    setResult(null);
    setScreen("processing");
    setIsLoading(true);
    try {
      const upload = await uploadDocument(file);
      setDocumentId(upload.document_id);
      const analysis = await analyzeDocument(upload.document_id);
      setResult(analysis);
    } catch (err) {
      const detail = err instanceof ApiRequestError ? err.message : "Unexpected error during analysis.";
      setErrorMessage(detail);
      setScreen("upload");
    } finally {
      setIsLoading(false);
    }
  }

  function reset() {
    setScreen("upload");
    setResult(null);
    setDocumentId(null);
    setErrorMessage(null);
  }

  return (
    <main className="mx-auto max-w-4xl px-4 py-10">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">ClauseGuard</h1>
        {screen !== "upload" && (
          <button onClick={reset} className="text-sm text-slate-500 hover:text-slate-700">
            ← Analyze another document
          </button>
        )}
      </div>

      <div className="mb-6">
        <Disclaimer />
      </div>

      {screen === "upload" && (
        <UploadScreen onFileSelected={handleFileSelected} errorMessage={errorMessage} />
      )}

      {screen === "processing" && (
        <ProcessingScreen
          isLoading={isLoading}
          result={result}
          onContinue={() => setScreen("results")}
        />
      )}

      {screen === "results" && result && (
        <ResultsScreen
          result={result}
          onViewReport={() => setScreen("report")}
          onReview={() => setScreen("review")}
        />
      )}

      {screen === "review" && documentId && (
        <ReviewScreen documentId={documentId} onBack={() => setScreen("results")} />
      )}

      {screen === "report" && documentId && result && (
        <ReportScreen
          documentId={documentId}
          filename={result.filename}
          onBack={() => setScreen("results")}
        />
      )}
    </main>
  );
}
