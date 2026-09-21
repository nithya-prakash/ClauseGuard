import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ReportScreen from "./ReportScreen";
import { ApiRequestError } from "@/lib/api";

const { downloadReportMock } = vi.hoisted(() => ({ downloadReportMock: vi.fn() }));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, downloadReport: downloadReportMock };
});

describe("ReportScreen", () => {
  beforeEach(() => {
    downloadReportMock.mockReset();
    // jsdom doesn't implement these - the component calls them to trigger
    // a real browser download.
    global.URL.createObjectURL = vi.fn(() => "blob:mock-url");
    global.URL.revokeObjectURL = vi.fn();
  });

  it("shows a loading message, then downloads the PDF and shows a ready state", async () => {
    downloadReportMock.mockResolvedValue(new Blob(["%PDF-1.4"], { type: "application/pdf" }));
    render(<ReportScreen documentId="doc1" filename="contract.pdf" onBack={vi.fn()} />);

    expect(screen.getByText("Generating report…")).toBeInTheDocument();

    await waitFor(() => expect(screen.getByText("Report downloaded.")).toBeInTheDocument());
    expect(downloadReportMock).toHaveBeenCalledWith("doc1");
    expect(global.URL.createObjectURL).toHaveBeenCalled();
  });

  it("shows a real error message when report generation fails, not a silent failure", async () => {
    downloadReportMock.mockRejectedValue(
      new ApiRequestError(404, "Document 'doc1' has not been analyzed yet.")
    );
    render(<ReportScreen documentId="doc1" filename="contract.pdf" onBack={vi.fn()} />);

    await waitFor(() =>
      expect(screen.getByText("Document 'doc1' has not been analyzed yet.")).toBeInTheDocument()
    );
  });

  it("falls back to a generic message for a non-API error", async () => {
    downloadReportMock.mockRejectedValue(new Error("network down"));
    render(<ReportScreen documentId="doc1" filename="contract.pdf" onBack={vi.fn()} />);

    await waitFor(() =>
      expect(screen.getByText("Could not generate the report.")).toBeInTheDocument()
    );
  });
});
