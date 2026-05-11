"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, ProcessDetailResponse } from "@/lib/api";

// ---------------------------------------------------------------------------
// Confidence summary card
// ---------------------------------------------------------------------------

function ConfidenceSummary({
  summary,
}: {
  summary: Record<string, number>;
}) {
  const items = [
    { label: "Workflow Steps", key: "workflow_step_count" },
    { label: "Roles", key: "role_count" },
    { label: "Systems", key: "system_touchpoint_count" },
    { label: "Controls", key: "control_count" },
    { label: "Decisions", key: "decision_point_count" },
    { label: "Exceptions", key: "exception_count" },
    { label: "Changes", key: "change_event_count" },
  ];
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
      {items.map(({ label, key }) => (
        <div
          key={key}
          className="bg-white border border-gray-200 rounded-lg p-3 text-center"
        >
          <div className="text-2xl font-bold text-gray-900">
            {summary[key] ?? 0}
          </div>
          <div className="text-xs text-gray-500 mt-0.5">{label}</div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main process detail page
// ---------------------------------------------------------------------------

export default function ProcessDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<ProcessDetailResponse | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    async function load() {
      try {
        const result = await api.getProcess(id);
        if (!cancelled) setData(result);
      } catch (e) {
        if (!cancelled)
          setError(e instanceof Error ? e.message : "Failed to load process");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (loading) return <div className="p-8 text-gray-500">Loading process…</div>;
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

  const ir = data.process_ir as Record<string, unknown> | null;

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <a
          href="/processes"
          className="text-xs text-gray-500 hover:text-gray-700"
        >
          ← All processes
        </a>
        <h1 className="text-2xl font-bold text-gray-900 mt-1">Process Details</h1>
        <p className="text-xs text-gray-400 font-mono mt-0.5">{id}</p>
        {data.schema_version && (
          <p className="text-xs text-gray-500 mt-0.5">{data.schema_version}</p>
        )}
      </div>

      {/* Navigation actions */}
      <div className="flex gap-3 mb-6">
        <a
          href={`/processes/${id}/graph`}
          className="px-4 py-2 bg-purple-600 text-white text-sm rounded-lg hover:bg-purple-700 transition-colors"
        >
          View Graph
        </a>
        <a
          href={`/processes/${id}/timeline`}
          className="px-4 py-2 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700 transition-colors"
        >
          View Timeline
        </a>
        {data.run_id && (
          <a
            href={`/runs/${data.run_id}/review`}
            className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors"
          >
            Review
          </a>
        )}
      </div>

      {/* Confidence summary */}
      {data.confidence_summary && (
        <ConfidenceSummary summary={data.confidence_summary} />
      )}

      {/* ProcessIR sections */}
      {ir && (
        <div className="space-y-4">
          <ProcessIRSection
            title="Workflow Steps"
            items={(ir.workflow_steps as unknown[]) ?? []}
            renderItem={(s: Record<string, unknown>) => (
              <div>
                <span className="font-medium text-gray-900">{String(s.name)}</span>
                {Boolean(s.role) && (
                  <span className="ml-2 text-xs text-green-600">
                    Role: {String(s.role)}
                  </span>
                )}
                {Boolean(s.system) && (
                  <span className="ml-2 text-xs text-purple-600">
                    System: {String(s.system)}
                  </span>
                )}
                {s.sequence_order != null && (
                  <span className="ml-2 text-xs text-gray-400">
                    #{String(s.sequence_order)}
                  </span>
                )}
              </div>
            )}
          />
          <ProcessIRSection
            title="Roles"
            items={(ir.roles as unknown[]) ?? []}
            renderItem={(r: Record<string, unknown>) => (
              <span className="font-medium text-gray-900">{String(r.name)}</span>
            )}
          />
          <ProcessIRSection
            title="Systems"
            items={(ir.system_touchpoints as unknown[]) ?? []}
            renderItem={(t: Record<string, unknown>) => (
              <div>
                <span className="font-medium text-gray-900">
                  {String(t.system_name)}
                </span>
                {Boolean(t.interaction_type) && (
                  <span className="ml-2 text-xs text-gray-500">
                    {String(t.interaction_type)}
                  </span>
                )}
              </div>
            )}
          />
          <ProcessIRSection
            title="Controls"
            items={(ir.controls as unknown[]) ?? []}
            renderItem={(c: Record<string, unknown>) => (
              <div>
                <span className="font-medium text-gray-900">{String(c.name)}</span>
                {Boolean(c.control_type) && (
                  <span className="ml-2 text-xs text-yellow-600">
                    {String(c.control_type)}
                  </span>
                )}
              </div>
            )}
          />
          <ProcessIRSection
            title="Change Events"
            items={(ir.change_events as unknown[]) ?? []}
            renderItem={(e: Record<string, unknown>) => (
              <span className="font-medium text-gray-900">{String(e.name)}</span>
            )}
          />
        </div>
      )}

      {!ir && (
        <div className="text-gray-500 text-sm">
          No ProcessIR data available for this process.
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Reusable section component
// ---------------------------------------------------------------------------

function ProcessIRSection({
  title,
  items,
  renderItem,
}: {
  title: string;
  items: unknown[];
  renderItem: (item: Record<string, unknown>) => React.ReactNode;
}) {
  if (items.length === 0) return null;
  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
      <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-700">{title}</h3>
        <span className="text-xs text-gray-400">{items.length}</span>
      </div>
      <ul className="divide-y divide-gray-100">
        {items.map((item, i) => (
          <li key={i} className="px-4 py-2.5 text-sm text-gray-800">
            {renderItem(item as Record<string, unknown>)}
          </li>
        ))}
      </ul>
    </div>
  );
}
