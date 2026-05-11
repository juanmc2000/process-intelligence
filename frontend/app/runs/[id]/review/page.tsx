"use client";

import { useEffect, useState } from "react";
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

// Map of entity_id -> review_state from existing entity reviews
type ReviewStateMap = Record<string, string>;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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
// Section component: renders a group of entities
// ---------------------------------------------------------------------------

function EntitySection<T extends BaseEntity>({
  title,
  items,
  entityType,
  reviewMap,
  renderExtra,
}: {
  title: string;
  items: T[];
  entityType: string;
  reviewMap: ReviewStateMap;
  renderExtra?: (item: T) => React.ReactNode;
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
          <div
            key={item.id}
            className="border border-gray-200 rounded p-3 bg-white text-xs space-y-1"
          >
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-medium">{item.name}</span>
              <span className="text-gray-400 font-mono">{item.id}</span>
              <span className="text-gray-400 text-xs">
                [{entityType}]
              </span>
              {reviewBadge(reviewMap[item.id])}
            </div>
            {item.description && (
              <p className="text-gray-600">{item.description}</p>
            )}
            {renderExtra?.(item)}
          </div>
        ))}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

/**
 * ProcessIR review screen — displays extracted entities grouped by category.
 * Shows confidence counts, review status per entity, and entity details.
 * Displays structured ProcessIR data only — no raw customer content.
 */
export default function ReviewPage() {
  const params = useParams();
  const runId = params.id as string;

  const [ir, setIr] = useState<ProcessIRResponse | null>(null);
  const [review, setReview] = useState<ReviewSummaryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [irData, reviewData] = await Promise.all([
          api.getProcessIR(runId),
          api.getReview(runId),
        ]);
        setIr(irData);
        setReview(reviewData);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load");
      }
    };
    load();
  }, [runId]);

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
  const reviewMap = buildReviewStateMap(review?.entity_reviews ?? []);
  const summary = ir.confidence_summary ?? {};

  // Type-cast arrays from untyped process_ir JSON
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

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold mb-1">ProcessIR Review</h1>
        <p className="text-xs font-mono text-gray-400">{runId}</p>
      </div>

      {/* Summary counts */}
      <section className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
        {Object.entries(summary).map(([key, val]) => (
          <div key={key} className="border border-gray-200 rounded p-3 bg-white">
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

      {/* Entity groups */}
      <EntitySection
        title="Workflow Steps"
        items={steps}
        entityType="workflow_step"
        reviewMap={reviewMap}
        renderExtra={(s: WorkflowStep) => (
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
        reviewMap={reviewMap}
      />

      <EntitySection
        title="Systems"
        items={systems}
        entityType="system_touchpoint"
        reviewMap={reviewMap}
        renderExtra={(s: SystemTouchpoint) => (
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
        reviewMap={reviewMap}
        renderExtra={(c: Control) =>
          c.control_type ? (
            <span className="text-gray-400">type: {c.control_type}</span>
          ) : null
        }
      />

      <EntitySection
        title="Change Events"
        items={changeEvents}
        entityType="change_event"
        reviewMap={reviewMap}
        renderExtra={(e: ChangeEvent) => (
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
        reviewMap={reviewMap}
        renderExtra={(d: DecisionPoint) => (
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
