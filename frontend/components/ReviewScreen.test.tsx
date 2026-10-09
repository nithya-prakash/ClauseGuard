import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ReviewScreen from "./ReviewScreen";
import type { ReviewedAnalysis } from "@/lib/types";

const { getReviewMock, submitReviewMock } = vi.hoisted(() => ({
  getReviewMock: vi.fn(),
  submitReviewMock: vi.fn(),
}));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, getReview: getReviewMock, submitReview: submitReviewMock };
});

const before: ReviewedAnalysis = {
  filename: "c.pdf",
  clauses: [
    { clause_id: "ok", risk_level: "LOW", review_reasons: [], review_status: "AUTO_ACCEPTED", reviewer_note: null },
    { clause_id: "hi", risk_level: "HIGH", review_reasons: ["risk_high"], review_status: "UNREVIEWED", reviewer_note: null },
  ],
  summary: { AUTO_ACCEPTED: 1, UNREVIEWED: 1 },
  fully_reviewed: false,
};
const after: ReviewedAnalysis = {
  ...before,
  clauses: [before.clauses[0], { ...before.clauses[1], review_status: "ESCALATE", reviewer_note: "lawyer" }],
  summary: { AUTO_ACCEPTED: 1, ESCALATE: 1 },
  fully_reviewed: true,
};

describe("ReviewScreen", () => {
  beforeEach(() => vi.clearAllMocks());

  it("lists only flagged clauses and submits a decision with its note", async () => {
    getReviewMock.mockResolvedValue(before);
    submitReviewMock.mockResolvedValue(after);
    render(<ReviewScreen documentId="d1" onBack={() => {}} />);

    expect(await screen.findByText("hi")).toBeTruthy();
    expect(screen.queryByText("ok")).toBeNull();

    fireEvent.change(screen.getByLabelText("Note for hi"), { target: { value: "lawyer" } });
    fireEvent.click(screen.getByText("ESCALATE"));

    await waitFor(() =>
      expect(submitReviewMock).toHaveBeenCalledWith("d1", { hi: { decision: "ESCALATE", note: "lawyer" } }),
    );
    expect(await screen.findByText(/all reviewed/)).toBeTruthy();
  });

  it("shows an error when loading fails", async () => {
    getReviewMock.mockRejectedValue(new Error("boom"));
    render(<ReviewScreen documentId="d1" onBack={() => {}} />);
    expect(await screen.findByText(/Could not load the review/)).toBeTruthy();
  });
});
