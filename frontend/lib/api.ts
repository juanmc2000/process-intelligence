/**
 * Typed API client for the Process Intelligence backend.
 *
 * The base URL is read from the NEXT_PUBLIC_API_URL environment variable.
 * All requests return structured metadata only — no raw customer content.
 */

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8010";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface HealthResponse {
  status: string;
}

export interface ReadyResponse {
  status: string;
}

export interface SourceResponse {
  id: string;
  filename: string;
  content_type: string | null;
  size_bytes: number | null;
  input_hash: string | null;
  status: string;
  created_at: string;
}

export interface ArtifactResponse {
  id: string;
  artifact_type: string;
  object_uri: string;
  content_type: string | null;
  size_bytes: number | null;
  deletion_eligible: boolean;
  created_at: string;
}

export interface WorkflowEventResponse {
  id: string;
  event_type: string;
  payload: Record<string, unknown> | null;
  created_at: string;
}

export interface ExtractionSummaryResponse {
  extraction_run_id: string;
  status: string;
  process_ir_uri: string | null;
  schema_version: string | null;
}

export interface RunDetailResponse {
  id: string;
  status: string;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  sources: SourceResponse[];
  artifacts: ArtifactResponse[];
  workflow_events: WorkflowEventResponse[];
  extraction: ExtractionSummaryResponse | null;
}

export interface ProcessIRResponse {
  run_id: string;
  source_id: string | null;
  extraction_result_id: string | null;
  extraction_status: string;
  schema_version: string | null;
  process_ir: Record<string, unknown> | null;
  confidence_summary: Record<string, number> | null;
}

export interface UploadResponse {
  run_id: string;
  source_id: string;
}

export interface ReviewSummaryResponse {
  run_id: string;
  sessions: Record<string, unknown>[];
  entity_reviews: Record<string, unknown>[];
  relation_reviews: Record<string, unknown>[];
  taxonomy_feedback: Record<string, unknown>[];
}

export interface ReviewRecordResponse {
  id: string;
  data: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// HTTP helpers
// ---------------------------------------------------------------------------

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`GET ${path} failed (${res.status}): ${text}`);
  }
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`POST ${path} failed (${res.status}): ${text}`);
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// API methods
// ---------------------------------------------------------------------------

export const api = {
  /** Check API health */
  health(): Promise<HealthResponse> {
    return get<HealthResponse>("/health");
  },

  /** Check API readiness */
  ready(): Promise<ReadyResponse> {
    return get<ReadyResponse>("/ready");
  },

  /** Upload a file and start a processing run */
  async upload(file: File): Promise<UploadResponse> {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API_BASE}/upload`, {
      method: "POST",
      body: form,
      cache: "no-store",
    });
    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText);
      throw new Error(`Upload failed (${res.status}): ${text}`);
    }
    return res.json() as Promise<UploadResponse>;
  },

  /** Get run detail (status, sources, artifacts, events, extraction) */
  getRun(runId: string): Promise<RunDetailResponse> {
    return get<RunDetailResponse>(`/runs/${runId}`);
  },

  /** Get ProcessIR for a completed run */
  getProcessIR(runId: string): Promise<ProcessIRResponse> {
    return get<ProcessIRResponse>(`/runs/${runId}/process-ir`);
  },

  /** Get all review records for a run */
  getReview(runId: string): Promise<ReviewSummaryResponse> {
    return get<ReviewSummaryResponse>(`/runs/${runId}/review`);
  },

  /** Submit an entity review */
  reviewEntity(
    entityId: string,
    body: {
      run_id: string;
      entity_type: string;
      review_state: string;
      edited_label?: string;
      confidence_override?: number;
      reviewer_note?: string;
    }
  ): Promise<ReviewRecordResponse> {
    return post<ReviewRecordResponse>(`/reviews/entities/${entityId}`, body);
  },

  /** Submit a relation review */
  reviewRelation(
    relationId: string,
    body: {
      run_id: string;
      relation_type: string;
      source_entity_id: string;
      target_entity_id: string;
      review_state: string;
      edited_label?: string;
      reviewer_note?: string;
    }
  ): Promise<ReviewRecordResponse> {
    return post<ReviewRecordResponse>(`/reviews/relations/${relationId}`, body);
  },

  /** Submit taxonomy feedback */
  submitTaxonomyFeedback(body: {
    run_id: string;
    entity_type: string;
    entity_id: string;
    feedback_type: string;
    proposed_label?: string;
    notes?: string;
  }): Promise<ReviewRecordResponse> {
    return post<ReviewRecordResponse>("/reviews/taxonomy", body);
  },
};
