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

// ---------------------------------------------------------------------------
// Sprint 6: Process exploration types
// ---------------------------------------------------------------------------

export interface ProcessSummaryResponse {
  extraction_result_id: string;
  extraction_run_id: string;
  run_id: string;
  extraction_status: string;
  process_ir_uri: string | null;
  schema_version: string | null;
  filename: string | null;
  created_at: string;
}

export interface ProcessDetailResponse {
  extraction_result_id: string;
  run_id: string;
  schema_version: string | null;
  process_ir: Record<string, unknown> | null;
  confidence_summary: Record<string, number> | null;
}

export interface TimelineEvent {
  event_id: string;
  description: string;
  category: string;
  process_id: string;
  from_value: string | null;
  to_value: string | null;
  evidence_count: number;
}

export interface TimelineResponse {
  extraction_result_id: string;
  process_id: string | null;
  events: TimelineEvent[];
  summary: Record<string, unknown>;
}

export interface GraphResponse {
  extraction_result_id: string;
  graph: {
    processId: string;
    nodes: Array<{
      id: string;
      type: string;
      data: { label: string; [key: string]: unknown };
      position: { x: number; y: number };
    }>;
    edges: Array<{
      id: string;
      source: string;
      target: string;
      type: string;
      label?: string;
      animated?: boolean;
    }>;
    metadata: Record<string, unknown>;
  };
}

export interface ProcessGroupResponse {
  cluster_id: string;
  process_ids: string[];
  cohesion: number;
  recommend_merge: boolean;
  merge_note: string | null;
}

export interface ProcessGroupsResponse {
  groups: ProcessGroupResponse[];
  singleton_count: number;
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
    form.append("files", file);
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

  /** List all process candidates */
  listProcesses(
    params: { limit?: number; offset?: number } = {}
  ): Promise<ProcessSummaryResponse[]> {
    const qs = new URLSearchParams();
    if (params.limit !== undefined) qs.set("limit", String(params.limit));
    if (params.offset !== undefined) qs.set("offset", String(params.offset));
    const query = qs.toString();
    return get<ProcessSummaryResponse[]>(`/processes${query ? `?${query}` : ""}`);
  },

  /** Get a single process by extraction_result_id */
  getProcess(id: string): Promise<ProcessDetailResponse> {
    return get<ProcessDetailResponse>(`/processes/${id}`);
  },

  /** Get the change timeline for a process */
  getProcessTimeline(id: string): Promise<TimelineResponse> {
    return get<TimelineResponse>(`/processes/${id}/timeline`);
  },

  /** Get the React Flow graph for a process */
  getProcessGraph(id: string): Promise<GraphResponse> {
    return get<GraphResponse>(`/processes/${id}/graph`);
  },

  /** Get similarity-based process groups */
  getProcessGroups(threshold?: number): Promise<ProcessGroupsResponse> {
    const qs = threshold !== undefined ? `?threshold=${threshold}` : "";
    return get<ProcessGroupsResponse>(`/processes/groups${qs}`);
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
