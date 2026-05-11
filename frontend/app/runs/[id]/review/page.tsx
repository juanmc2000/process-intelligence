"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { api, ProcessIRResponse, ReviewSummaryResponse } from "@/lib/api";

// ---------------------------------------------------------------------------
// Types from ProcessIR JSON shape
// ---------------------------------------------------------------------------

interface EvidenceRef {
  artifact_uri: string;
  location_hint?: string;
}

interface BaseEntity {
  id: string;
  name: string;
  description?: string;
  evidence_refs?: EvidenceRef[];
}

interface WorkflowStep extends BaseEntity {
  sequence_order?: number;
  role?: string;
  system?: string;
}

// Role has no additional fields beyond BaseEntity
type Role = BaseEntity;

interface SystemTouchpoint extends BaseEntity {
  system_name: string;
  interaction_type?: string;
}

interface Control extends BaseEntity {
  control_type?: string;
}

interface ChangeEvent extends BaseEntity {
  trigger?: string;
  impact?: string;
}

interface DecisionPoint extends BaseEntity {
  conditions?: string[];
  outcomes?: string[];
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// Map of entity_id -> review_state from persisted entity reviews
type ReviewStateMap = Record<string, string>;

function buildReviewStateMap(
  entityReviews: Record<string, unknown>[]
): ReviewStateMap {
  const map: ReviewStateMap = {};
  for (const r of entityReviews) {
    const id = r["entity_id"] as string | undefined;
    const state = r["review_state"] as string | undefined;
    if (id && state) map[id] = state;
  }
  return map;
}

function reviewBadge(state: string | undefined) {
  if (!state) return null;
  const colors: Record<string, string> = {
    accepted: "bg-green-100 text-green-700",
    rejected: "bg-red-100 text-red-700",
    edited: "bg-blue-100 text-blue-700",
    merged: "bg-purple-100 text-purple-700",
    split: "bg-orange-100 text-orange-700",
    confidence_override: "bg-yellow-100 text-yellow-700",
  };
  const cls = colors[state] ?? "bg-gray-100 text-gray-700";
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${cls}`}>
      {state}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Edit form: inline label editing and confidence override
// ---------------------------------------------------------------------------

interface EditFormProps {
  entityId: string;
  entityType: string;
  runId: string;
  originalLabel: string;
  onSave: (entityId: string) => void;
  onCancel: () => void;
}

function EditForm({
  entityId,
  entityType,
  runId,
  originalLabel,
  onSave,
  onCancel,
}: EditFormProps) {
  const [label, setLabel] = useState(originalLabel);
  const [confidence, setConfidence] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const body: Parameters<typeof api.reviewEntity>[1] = {
        run_id: runId,
        entity_type: entityType,
        review_state: confidence ? "confidence_override" : "edited",
        edited_label: label !== originalLabel ? label : undefined,
        confidence_override: confidence ? Number(confidence) : undefined,
        reviewer_note: note || undefined,
      };
      await api.reviewEntity(entityId, body);
      onSave(entityId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
      setSaving(false);
    }
  };

  return (
    <div className="mt-2 border-t border-gray-100 pt-2 space-y-2">
      <div>
        <label className="block text-xs text-gray-500 mb-1">Label</label>
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          className="w-full text-xs border border-gray-300 rounded px-2 py-1"
        />
      </div>
      <div>
        <label className="block text-xs text-gray-500 mb-1">
          Confidence override (0–1, optional)
        </label>
        <input
          type="number"
          min="0"
          max="1"
          step="0.01"
          value={confidence}
          onChange={(e) => setConfidence(e.target.value)}
          placeholder="e.g. 0.85"
          className="w-32 text-xs border border-gray-300 rounded px-2 py-1"
        />
      </div>
      <div>
        <label className="block text-xs text-gray-500 mb-1">
          Reviewer note (optional)
        </label>
        <input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          className="w-full text-xs border border-gray-300 rounded px-2 py-1"
        />
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="flex gap-2">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-3 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save"}
        </button>
        <button
          onClick={onCancel}
          className="px-3 py-1 border border-gray-300 text-xs rounded hover:bg-gray-50"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Taxonomy feedback form
// ---------------------------------------------------------------------------

interface TaxonomyFeedbackFormProps {
  runId: string;
  entityId: string;
  entityType: string;
  onDone: () => void;
}

function TaxonomyFeedbackForm({
  runId,
  entityId,
  entityType,
  onDone,
}: TaxonomyFeedbackFormProps) {
  const [feedbackType, setFeedbackType] = useState("new_label");
  const [proposedLabel, setProposedLabel] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    setSaving(true);
    setError(null);
    try {
      await api.submitTaxonomyFeedback({
        run_id: runId,
        entity_type: entityType,
        entity_id: entityId,
        feedback_type: feedbackType,
        proposed_label: proposedLabel || undefined,
        notes: notes || undefined,
      });
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submit failed");
      setSaving(false);
    }
  };

  return (
    <div className="mt-2 border-t border-gray-100 pt-2 space-y-2">
      <div>
        <label className="block text-xs text-gray-500 mb-1">
          Feedback type
        </label>
        <select
          value={feedbackType}
          onChange={(e) => setFeedbackType(e.target.value)}
          className="text-xs border border-gray-300 rounded px-2 py-1"
        >
          <option value="new_label">New label</option>
          <option value="merge_suggestion">Merge suggestion</option>
          <option value="split_suggestion">Split suggestion</option>
          <option value="other">Other</option>
        </select>
      </div>
      <div>
        <label className="block text-xs text-gray-500 mb-1">
          Proposed label (optional)
        </label>
        <input
          value={proposedLabel}
          onChange={(e) => setProposedLabel(e.target.value)}
          className="w-full text-xs border border-gray-300 rounded px-2 py-1"
        />
      </div>
      <div>
        <label className="block text-xs text-gray-500 mb-1">Notes</label>
        <input
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          className="w-full text-xs border border-gray-300 rounded px-2 py-1"
        />
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="flex gap-2">
        <button
          onClick={handleSubmit}
          disabled={saving}
          className="px-3 py-1 bg-purple-600 text-white text-xs rounded hover:bg-purple-700 disabled:opacity-50"
        >
          {saving ? "Submitting…" : "Submit feedback"}
        </button>
        <button
          onClick={onDone}
          className="px-3 py-1 border border-gray-300 text-xs rounded hover:bg-gray-50"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Entity card with accept / reject / edit / taxonomy-feedback controls
// ---------------------------------------------------------------------------

interface EntityCardProps<T extends BaseEntity> {
  item: T;
  entityType: string;
  runId: string;
  reviewState: string | undefined;
  onReviewed: (entityId: string, newState: string) => void;
  renderDetail?: (item: T) => React.ReactNode;
}

function EntityCard<T extends BaseEntity>({
  item,
  entityType,
  runId,
  reviewState,
  onReviewed,
  renderDetail,
}: EntityCardProps<T>) {
  const [mode, setMode] = useState<"view" | "edit" | "taxonomy">("view");
  const [localState, setLocalState] = useState(reviewState);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Simple accept/reject action
  const doReview = async (state: "accepted" | "rejected") => {
    setBusy(true);
    setError(null);
    try {
      await api.reviewEntity(item.id, {
        run_id: runId,
        entity_type: entityType,
        review_state: state,
        reviewer_note: `original: ${item.name}`,
      });
      setLocalState(state);
      onReviewed(item.id, state);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusy(false);
    }
  };

  const handleEditSave = (entityId: string) => {
    const newState =
      localState === "confidence_override" ? "confidence_override" : "edited";
    setLocalState(newState);
    onReviewed(entityId, newState);
    setMode("view");
  };

  const handleTaxonomyDone = () => {
    setMode("view");
  };

  return (
    <div className="border border-gray-200 rounded p-3 bg-white text-xs space-y-1">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="font-medium">{item.name}</span>
        <span className="text-gray-400 font-mono">{item.id}</span>
        <span className="text-gray-400">[{entityType}]</span>
        {reviewBadge(localState)}
      </div>

      {item.description && <p className="text-gray-600">{item.description}</p>}
      {renderDetail?.(item)}

      {error && <p className="text-red-600">{error}</p>}

      {/* Review action buttons */}
      {mode === "view" && (
        <div className="flex gap-2 pt-1 flex-wrap">
          <button
            onClick={() => doReview("accepted")}
            disabled={busy}
            className="px-2 py-1 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
          >
            Accept
          </button>
          <button
            onClick={() => doReview("rejected")}
            disabled={busy}
            className="px-2 py-1 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
          >
            Reject
          </button>
          <button
            onClick={() => setMode("edit")}
            disabled={busy}
            className="px-2 py-1 border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50"
          >
            Edit
          </button>
          <button
            onClick={() => setMode("taxonomy")}
            disabled={busy}
            className="px-2 py-1 border border-purple-300 text-purple-700 rounded hover:bg-purple-50 disabled:opacity-50"
          >
            Taxonomy feedback
          </button>
        </div>
      )}

      {mode === "edit" && (
        <EditForm
          entityId={item.id}
          entityType={entityType}
          runId={runId}
          originalLabel={item.name}
          onSave={handleEditSave}
          onCancel={() => setMode("view")}
        />
      )}

      {mode === "taxonomy" && (
        <TaxonomyFeedbackForm
          runId={runId}
          entityId={item.id}
          entityType={entityType}
          onDone={handleTaxonomyDone}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Entity section wrapper
// ---------------------------------------------------------------------------

function EntitySection<T extends BaseEntity>({
  title,
  items,
  entityType,
  runId,
  reviewMap,
  onReviewed,
  renderDetail,
}: {
  title: string;
  items: T[];
  entityType: string;
  runId: string;
  reviewMap: ReviewStateMap;
  onReviewed: (entityId: string, newState: string) => void;
  renderDetail?: (item: T) => React.ReactNode;
}) {
  if (items.length === 0) return null;
  return (
    <section>
      <h2 className="text-sm font-semibold mb-2 text-gray-700">
        {title}
        <span className="ml-2 text-xs font-normal text-gray-400">
          ({items.length})
        </span>
      </h2>
      <div className="space-y-2">
        {items.map((item) => (
          <EntityCard
            key={item.id}
            item={item}
            entityType={entityType}
            runId={runId}
            reviewState={reviewMap[item.id]}
            onReviewed={onReviewed}
            renderDetail={renderDetail}
          />
        ))}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

/**
 * ProcessIR review screen with accept / reject / edit controls per entity
 * and taxonomy feedback forms. After each review action the UI updates
 * immediately without a full reload.
 *
 * Displays structured ProcessIR data only — no raw customer content.
 */
export default function ReviewPage() {
  const params = useParams();
  const runId = params.id as string;

  const [ir, setIr] = useState<ProcessIRResponse | null>(null);
  const [review, setReview] = useState<ReviewSummaryResponse | null>(null);
  const [reviewMap, setReviewMap] = useState<ReviewStateMap>({});
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [irData, reviewData] = await Promise.all([
        api.getProcessIR(runId),
        api.getReview(runId),
      ]);
      setIr(irData);
      setReview(reviewData);
      setReviewMap(buildReviewStateMap(reviewData.entity_reviews));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    }
  }, [runId]);

  useEffect(() => {
    load();
  }, [load]);

  // Update the local review map when a user submits a review action
  const handleReviewed = useCallback((entityId: string, newState: string) => {
    setReviewMap((prev) => ({ ...prev, [entityId]: newState }));
  }, []);

  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (!ir) return <p className="text-sm text-gray-500">Loading…</p>;

  if (ir.extraction_status !== "completed" || !ir.process_ir) {
    return (
      <div className="max-w-lg">
        <h1 className="text-xl font-semibold mb-2">ProcessIR Review</h1>
        <p className="text-sm text-gray-500">
          Extraction status:{" "}
          <span className="font-mono">{ir.extraction_status}</span>
        </p>
      </div>
    );
  }

  const data = ir.process_ir as Record<string, unknown>;
  const summary = ir.confidence_summary ?? {};

  const steps = (data.workflow_steps ?? []) as WorkflowStep[];
  const roles = (data.roles ?? []) as Role[];
  const systems = (data.system_touchpoints ?? []) as SystemTouchpoint[];
  const controls = (data.controls ?? []) as Control[];
  const changeEvents = (data.change_events ?? []) as ChangeEvent[];
  const decisions = (data.decision_points ?? []) as DecisionPoint[];

  const totalEntities =
    steps.length +
    roles.length +
    systems.length +
    controls.length +
    changeEvents.length +
    decisions.length;

  const reviewedCount = Object.keys(reviewMap).length;

  // Suppress the unused review warning (used for initial build)
  void review;

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold mb-1">ProcessIR Review</h1>
        <p className="text-xs font-mono text-gray-400">{runId}</p>
      </div>

      {/* Summary counts */}
      <section className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
        {Object.entries(summary).map(([key, val]) => (
          <div
            key={key}
            className="border border-gray-200 rounded p-3 bg-white"
          >
            <div className="text-gray-500 mb-1">
              {key.replace(/_count$/, "").replace(/_/g, " ")}
            </div>
            <div className="text-lg font-semibold">{val as number}</div>
          </div>
        ))}
        <div className="border border-gray-200 rounded p-3 bg-white">
          <div className="text-gray-500 mb-1">reviewed</div>
          <div className="text-lg font-semibold">
            {reviewedCount}/{totalEntities}
          </div>
        </div>
      </section>

      {/* Entity sections with review controls */}
      <EntitySection
        title="Workflow Steps"
        items={steps}
        entityType="workflow_step"
        runId={runId}
        reviewMap={reviewMap}
        onReviewed={handleReviewed}
        renderDetail={(s: WorkflowStep) => (
          <div className="text-gray-400 space-x-3">
            {s.sequence_order != null && (
              <span>order: {s.sequence_order}</span>
            )}
            {s.role && <span>role: {s.role}</span>}
            {s.system && <span>system: {s.system}</span>}
          </div>
        )}
      />

      <EntitySection
        title="Roles"
        items={roles}
        entityType="role"
        runId={runId}
        reviewMap={reviewMap}
        onReviewed={handleReviewed}
      />

      <EntitySection
        title="Systems"
        items={systems}
        entityType="system_touchpoint"
        runId={runId}
        reviewMap={reviewMap}
        onReviewed={handleReviewed}
        renderDetail={(s: SystemTouchpoint) => (
          <div className="text-gray-400 space-x-3">
            <span>system: {s.system_name}</span>
            {s.interaction_type && (
              <span>interaction: {s.interaction_type}</span>
            )}
          </div>
        )}
      />

      <EntitySection
        title="Controls"
        items={controls}
        entityType="control"
        runId={runId}
        reviewMap={reviewMap}
        onReviewed={handleReviewed}
        renderDetail={(c: Control) =>
          c.control_type ? (
            <span className="text-gray-400">type: {c.control_type}</span>
          ) : null
        }
      />

      <EntitySection
        title="Change Events"
        items={changeEvents}
        entityType="change_event"
        runId={runId}
        reviewMap={reviewMap}
        onReviewed={handleReviewed}
        renderDetail={(e: ChangeEvent) => (
          <div className="text-gray-400 space-x-3">
            {e.trigger && <span>trigger: {e.trigger}</span>}
            {e.impact && <span>impact: {e.impact}</span>}
          </div>
        )}
      />

      <EntitySection
        title="Decision Points"
        items={decisions}
        entityType="decision_point"
        runId={runId}
        reviewMap={reviewMap}
        onReviewed={handleReviewed}
        renderDetail={(d: DecisionPoint) => (
          <div className="text-gray-400">
            {d.conditions && d.conditions.length > 0 && (
              <div>conditions: {d.conditions.join(", ")}</div>
            )}
            {d.outcomes && d.outcomes.length > 0 && (
              <div>outcomes: {d.outcomes.join(", ")}</div>
            )}
          </div>
        )}
      />
    </div>
  );
}
