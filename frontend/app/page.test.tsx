import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Home from "./page";
import { ApiRequestError } from "@/lib/api";
import type { DocumentAnalysisResult, UploadResponse } from "@/lib/types";

const { uploadDocumentMock, analyzeDocumentMock } = vi.hoisted(() => ({
  uploadDocumentMock: vi.fn(),
  analyzeDocumentMock: vi.fn(),
}));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    uploadDocument: uploadDocumentMock,
    analyzeDocument: analyzeDocumentMock,
  };
});

const UPLOAD_RESPONSE: UploadResponse = {
  document_id: "doc1",
  filename: "contract.pdf",
  size_bytes: 1234,
};

const ANALYSIS_RESULT: DocumentAnalysisResult = {
  filename: "contract.pdf",
  analyzed_at: "2026-09-20T12:00:00Z",
  clause_count: 1,
  clauses: [
    {
      clause: {
        clause_id: "c1",
        text: "Der Auftragnehmer haftet nur für Vorsatz und grobe Fahrlässigkeit.",
        section: "§ 4",
        heading: "Haftung",
        page_start: 1,
        page_end: 1,
        position: 4,
      },
      classification: { clause_type: "LIABILITY", confidence: 0.9, model_name: "lora" },
      classification_error: null,
      reasoning: null,
      reasoning_error: "Set LLM_PROVIDER=anthropic and ANTHROPIC_API_KEY to enable reasoning.",
    },
  ],
};

function selectFile(file: File) {
  const input = screen.getByTestId("file-input") as HTMLInputElement;
  fireEvent.change(input, { target: { files: [file] } });
}

describe("Home (full upload -> processing -> results flow)", () => {
  beforeEach(() => {
    uploadDocumentMock.mockReset();
    analyzeDocumentMock.mockReset();
  });

  it("walks a successful upload through processing to the results screen", async () => {
    uploadDocumentMock.mockResolvedValue(UPLOAD_RESPONSE);
    analyzeDocumentMock.mockResolvedValue(ANALYSIS_RESULT);
    render(<Home />);

    selectFile(new File(["x"], "contract.pdf", { type: "application/pdf" }));

    // Processing screen appears with the real computed stage checkmarks.
    await waitFor(() => expect(screen.getByText("View results")).toBeInTheDocument());
    expect(uploadDocumentMock).toHaveBeenCalledTimes(1);
    expect(analyzeDocumentMock).toHaveBeenCalledWith("doc1");

    fireEvent.click(screen.getByText("View results"));

    expect(screen.getByText("contract.pdf")).toBeInTheDocument();
    expect(screen.getByText("§ 4")).toBeInTheDocument();
  });

  it("shows a real error and returns to the upload screen when analysis fails", async () => {
    uploadDocumentMock.mockResolvedValue(UPLOAD_RESPONSE);
    analyzeDocumentMock.mockRejectedValue(
      new ApiRequestError(422, "Could not parse the uploaded file - it may be corrupted.")
    );
    render(<Home />);

    selectFile(new File(["x"], "contract.pdf", { type: "application/pdf" }));

    await waitFor(() =>
      expect(
        screen.getByText("Could not parse the uploaded file - it may be corrupted.")
      ).toBeInTheDocument()
    );
    // Back on the upload screen, not stuck on processing or a blank results screen.
    expect(screen.getByText("Upload a contract")).toBeInTheDocument();
  });

  it("shows a generic error for a non-API failure rather than an unhandled crash", async () => {
    uploadDocumentMock.mockRejectedValue(new TypeError("Failed to fetch"));
    render(<Home />);

    selectFile(new File(["x"], "contract.pdf", { type: "application/pdf" }));

    await waitFor(() =>
      expect(screen.getByText("Unexpected error during analysis.")).toBeInTheDocument()
    );
  });

  it("resets to the upload screen via 'Analyze another document'", async () => {
    uploadDocumentMock.mockResolvedValue(UPLOAD_RESPONSE);
    analyzeDocumentMock.mockResolvedValue(ANALYSIS_RESULT);
    render(<Home />);

    selectFile(new File(["x"], "contract.pdf", { type: "application/pdf" }));
    await waitFor(() => expect(screen.getByText("View results")).toBeInTheDocument());

    fireEvent.click(screen.getByText("← Analyze another document"));
    expect(screen.getByText("Upload a contract")).toBeInTheDocument();
  });
});
