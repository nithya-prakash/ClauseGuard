import type { ApiError, Clause, DocumentAnalysisResult, UploadResponse } from "./types";

// Server-side (Docker network) vs. browser-side (host machine) need different
// base URLs - the backend container is reachable as "backend:8000" inside
// Docker's network but only as "localhost:8004" (the host-mapped port, see
// docker-compose.yml) from the browser running on the developer's machine.
// NEXT_PUBLIC_ vars are inlined at build time and are what the browser uses.
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8004";

export class ApiRequestError extends Error {
  status: number;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const body = (await response.json()) as ApiError;
      if (body.detail) detail = body.detail;
    } catch {
      // response body wasn't JSON - keep the generic message
    }
    throw new ApiRequestError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

export async function uploadDocument(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE_URL}/documents`, {
    method: "POST",
    body: formData,
  });
  return handleResponse<UploadResponse>(response);
}

export async function analyzeDocument(documentId: string): Promise<DocumentAnalysisResult> {
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}/analyze`, {
    method: "POST",
  });
  return handleResponse<DocumentAnalysisResult>(response);
}

export async function getFindings(documentId: string): Promise<DocumentAnalysisResult> {
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}/findings`);
  return handleResponse<DocumentAnalysisResult>(response);
}

export async function getClauses(documentId: string): Promise<Clause[]> {
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}/clauses`);
  return handleResponse<Clause[]>(response);
}

export async function getReportStatus(documentId: string): Promise<never> {
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}/report`);
  return handleResponse<never>(response);
}
