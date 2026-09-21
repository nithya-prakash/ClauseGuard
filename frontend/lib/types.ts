// Mirrors backend/app/schemas/{pipeline,reasoning,verification,clause,classification}.py.
// Kept in sync by hand (no shared codegen yet) - a real limitation, not an
// oversight; see README "Known limitations".

export interface Clause {
  clause_id: string;
  text: string;
  section: string | null;
  heading: string | null;
  page_start: number | null;
  page_end: number | null;
  position: number;
}

export interface ClassificationResult {
  clause_type: string;
  confidence: number;
  model_name: string;
}

export type CitationStatus = "VERIFIED" | "CITATION_UNVERIFIED";

export interface VerifiedFinding {
  claim: string;
  legal_basis: string;
  citation: string;
  evidence: string;
  citation_status: CitationStatus;
  citation_reason: string | null;
}

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "INSUFFICIENT_EVIDENCE";
export type ReasoningStatus = "OK" | "REVIEW_RECOMMENDED" | "INSUFFICIENT_EVIDENCE";

export interface ReasoningResult {
  clause_id: string;
  classification: string;
  risk_level: RiskLevel;
  status: ReasoningStatus;
  findings: VerifiedFinding[];
  explanation: string;
  confidence: "LOW" | "MEDIUM" | "HIGH";
  limitations: string[];
}

export interface ClauseAnalysis {
  clause: Clause;
  classification: ClassificationResult | null;
  classification_error: string | null;
  reasoning: ReasoningResult | null;
  reasoning_error: string | null;
}

export interface DocumentAnalysisResult {
  filename: string;
  analyzed_at: string;
  clause_count: number;
  clauses: ClauseAnalysis[];
}

export interface UploadResponse {
  document_id: string;
  filename: string;
  size_bytes: number;
}

export interface ApiError {
  detail: string;
}
