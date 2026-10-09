import { afterEach, describe, expect, it, vi } from "vitest";
import { analyzeDocument } from "./api";

const json = (body: unknown, status = 200) =>
  Promise.resolve(new Response(JSON.stringify(body), { status }));

afterEach(() => vi.unstubAllGlobals());

describe("analyzeDocument (async job path)", () => {
  it("creates a job and polls until completed", async () => {
    const result = { filename: "c.pdf", analyzed_at: "now", clause_count: 0, clauses: [] };
    const fetchMock = vi
      .fn()
      .mockReturnValueOnce(json({ job_id: "j1", status: "PENDING" }, 202))
      .mockReturnValueOnce(json({ job_id: "j1", status: "RUNNING" }))
      .mockReturnValueOnce(json({ job_id: "j1", status: "COMPLETED", result }));
    vi.stubGlobal("fetch", fetchMock);
    vi.useFakeTimers();
    const promise = analyzeDocument("d1");
    await vi.runAllTimersAsync();
    vi.useRealTimers();
    expect(await promise).toEqual(result);
    expect(fetchMock.mock.calls[0][0]).toContain("/documents/d1/jobs");
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "POST" });
  });

  it("throws the job error when the job fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockReturnValueOnce(json({ job_id: "j1", status: "PENDING" }, 202))
        .mockReturnValueOnce(json({ job_id: "j1", status: "FAILED", error: "bad pdf" })),
    );
    await expect(analyzeDocument("d1")).rejects.toThrow("bad pdf");
  });
});
