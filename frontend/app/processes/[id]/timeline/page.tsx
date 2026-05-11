"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, TimelineResponse, TimelineEvent } from "@/lib/api";

// ---------------------------------------------------------------------------
// Category colours
// ---------------------------------------------------------------------------

const CATEGORY_COLOURS: Record<string, string> = {
  role_change: "bg-blue-100 text-blue-700 border-blue-200",
  system_migration: "bg-purple-100 text-purple-700 border-purple-200",
  control_change: "bg-yellow-100 text-yellow-700 border-yellow-200",
  approval_change: "bg-orange-100 text-orange-700 border-orange-200",
  workflow_step_change: "bg-teal-100 text-teal-700 border-teal-200",
  general: "bg-gray-100 text-gray-700 border-gray-200",
};

const CATEGORY_LABELS: Record<string, string> = {
  role_change: "Role",
  system_migration: "System",
  control_change: "Control",
  approval_change: "Approval",
  workflow_step_change: "Workflow",
  general: "General",
};

// ---------------------------------------------------------------------------
// Category badge
// ---------------------------------------------------------------------------

function CategoryBadge({ category }: { category: string }) {
  const cls = CATEGORY_COLOURS[category] ?? "bg-gray-100 text-gray-700 border-gray-200";
  const label = CATEGORY_LABELS[category] ?? category;
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded text-xs font-medium border ${cls}`}
    >
      {label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Timeline event card
// ---------------------------------------------------------------------------

function EventCard({ event }: { event: TimelineEvent }) {
  return (
    <div className="flex gap-4 pb-6 relative">
      {/* Connector line */}
      <div className="flex flex-col items-center">
        <div className="w-3 h-3 rounded-full bg-gray-400 border-2 border-white ring-2 ring-gray-300 mt-1 shrink-0" />
        <div className="w-px flex-1 bg-gray-200 mt-1" />
      </div>

      {/* Content */}
      <div className="flex-1 pb-2">
        <div className="flex items-start gap-2 flex-wrap">
          <CategoryBadge category={event.category} />
          {event.evidence_count > 0 && (
            <span className="text-xs text-gray-400">
              {event.evidence_count} evidence ref{event.evidence_count !== 1 ? "s" : ""}
            </span>
          )}
        </div>
        <p className="mt-1 text-sm text-gray-800 font-medium">{event.description}</p>
        {/* Show from → to if available */}
        {event.from_value && event.to_value && (
          <div className="mt-1 flex items-center gap-2 text-xs">
            <span className="bg-red-50 text-red-600 px-1.5 py-0.5 rounded font-mono">
              {event.from_value}
            </span>
            <span className="text-gray-400">→</span>
            <span className="bg-green-50 text-green-600 px-1.5 py-0.5 rounded font-mono">
              {event.to_value}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Summary panel
// ---------------------------------------------------------------------------

function SummaryPanel({ summary }: { summary: Record<string, unknown> }) {
  const categories = summary.change_categories as Record<string, number> | undefined;
  return (
    <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 mb-6 text-sm">
      <div className="grid grid-cols-2 gap-2">
        <div>
          <span className="text-gray-500">Versions tracked</span>
          <span className="ml-2 font-medium text-gray-900">
            {String(summary.version_count ?? 1)}
          </span>
        </div>
        <div>
          <span className="text-gray-500">Change events</span>
          <span className="ml-2 font-medium text-gray-900">
            {String(summary.total_change_events ?? 0)}
          </span>
        </div>
        {Boolean(summary.has_ambiguous_lineage) && (
          <div className="col-span-2 text-amber-600 text-xs">
            ⚠ Ambiguous lineage detected — manual review recommended.
          </div>
        )}
      </div>
      {categories && Object.keys(categories).length > 0 && (
        <div className="mt-3">
          <div className="text-xs text-gray-500 mb-1">By category</div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(categories)
              .filter(([, n]) => n > 0)
              .map(([cat, n]) => (
                <span key={cat} className="text-xs text-gray-700">
                  <CategoryBadge category={cat} />
                  <span className="ml-1 font-medium">{n}</span>
                </span>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main timeline page
// ---------------------------------------------------------------------------

export default function ProcessTimelinePage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<TimelineResponse | null>(null);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    async function load() {
      try {
        const result = await api.getProcessTimeline(id);
        if (!cancelled) setData(result);
      } catch (e) {
        if (!cancelled)
          setError(e instanceof Error ? e.message : "Failed to load timeline");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (loading) return <div className="p-8 text-gray-500">Loading timeline…</div>;
  if (error) {
    return (
      <div className="p-8">
        <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-lg">
          {error}
        </div>
      </div>
    );
  }
  if (!data) return null;

  const categories = Array.from(new Set(data.events.map((e) => e.category)));
  const visibleEvents = activeCategory
    ? data.events.filter((e) => e.category === activeCategory)
    : data.events;

  return (
    <div className="p-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div>
          <a
            href={`/processes/${id}`}
            className="text-xs text-gray-500 hover:text-gray-700"
          >
            ← Process details
          </a>
          <h1 className="text-2xl font-bold text-gray-900 mt-1">Change Timeline</h1>
          {data.process_id && (
            <p className="text-xs text-gray-400 font-mono mt-0.5">{data.process_id}</p>
          )}
        </div>
      </div>

      {/* Summary */}
      <SummaryPanel summary={data.summary} />

      {/* Category filter */}
      {categories.length > 1 && (
        <div className="flex flex-wrap gap-2 mb-4">
          <button
            onClick={() => setActiveCategory(null)}
            className={`text-xs px-2 py-1 rounded border transition-colors ${
              activeCategory === null
                ? "bg-gray-900 text-white border-gray-900"
                : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50"
            }`}
          >
            All
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat === activeCategory ? null : cat)}
              className={`text-xs px-2 py-1 rounded border transition-colors ${
                activeCategory === cat
                  ? "bg-gray-900 text-white border-gray-900"
                  : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50"
              }`}
            >
              {CATEGORY_LABELS[cat] ?? cat}
            </button>
          ))}
        </div>
      )}

      {/* Timeline */}
      {visibleEvents.length === 0 ? (
        <div className="text-gray-500 text-sm">No change events recorded.</div>
      ) : (
        <div>
          {visibleEvents.map((event) => (
            <EventCard key={event.event_id} event={event} />
          ))}
        </div>
      )}

      {/* Navigation */}
      <div className="mt-6 pt-4 border-t border-gray-200 flex gap-3">
        <a
          href={`/processes/${id}/graph`}
          className="text-xs px-3 py-1.5 bg-purple-50 text-purple-700 border border-purple-200 rounded hover:bg-purple-100"
        >
          View Graph
        </a>
        <a
          href="/processes"
          className="text-xs px-3 py-1.5 bg-gray-50 text-gray-700 border border-gray-200 rounded hover:bg-gray-100"
        >
          All Processes
        </a>
      </div>
    </div>
  );
}
