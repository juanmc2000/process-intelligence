"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, RunDetailResponse } from "@/lib/api";

/**
 * Run status page — shows run metadata, sources, artifacts, and extraction status.
 * Auto-refreshes while the run is in a non-terminal state.
 * Displays structured metadata only — no raw customer content.
 */
export default function RunPage() {
  const params = useParams();
  const runId = params.id as string;

  const [run, setRun] = useState<RunDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await api.getRun(runId);
      setRun(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load run");
    }
  }, [runId]);

  useEffect(() => {
    load();
    // Poll every 3 s while the run is still active
    const interval = setInterval(async () => {
      const data = await api.getRun(runId).catch(() => null);
      if (!data) return;
      setRun(data);
      // Stop polling once terminal
      if (["completed", "failed", "error"].includes(data.status)) {
        clearInterval(interval);
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [runId, load]);

  if (error) {
    return <p className="text-sm text-red-600">{error}</p>;
  }
  if (!run) {
    return <p className="text-sm text-gray-500">Loading…</p>;
  }

  const extractionDone =
    run.extraction?.status === "completed" && run.extraction.process_ir_uri;

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold mb-1">Run</h1>
        <p className="text-xs font-mono text-gray-500 break-all">{run.id}</p>
      </div>

      {/* Status badges */}
      <section className="flex gap-4 flex-wrap">
        <StatusBadge label="Run" value={run.status} />
        {run.extraction && (
          <StatusBadge label="Extraction" value={run.extraction.status} />
        )}
      </section>

      {run.error_message && (
        <p className="text-sm text-red-600">{run.error_message}</p>
      )}

      {/* Sources */}
      {run.sources.length > 0 && (
        <section>
          <h2 className="text-sm font-medium mb-2">Sources</h2>
          <table className="w-full text-xs border border-gray-200 rounded overflow-hidden">
            <thead className="bg-gray-100">
              <tr>
                <th className="text-left px-3 py-2">Filename</th>
                <th className="text-left px-3 py-2">Type</th>
                <th className="text-left px-3 py-2">Size</th>
                <th className="text-left px-3 py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {run.sources.map((s) => (
                <tr key={s.id} className="border-t border-gray-200">
                  <td className="px-3 py-2 font-mono">{s.filename}</td>
                  <td className="px-3 py-2 text-gray-500">
                    {s.content_type ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-gray-500">
                    {s.size_bytes != null
                      ? `${(s.size_bytes / 1024).toFixed(1)} KB`
                      : "—"}
                  </td>
                  <td className="px-3 py-2">{s.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {/* Extraction summary */}
      {run.extraction && (
        <section>
          <h2 className="text-sm font-medium mb-2">Extraction</h2>
          <dl className="text-xs space-y-1">
            <Row label="Status" value={run.extraction.status} />
            <Row
              label="Schema version"
              value={run.extraction.schema_version ?? "—"}
            />
          </dl>
          {extractionDone && (
            <div className="mt-3 flex gap-3">
              <Link
                href={`/runs/${runId}/review`}
                className="px-3 py-1.5 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 transition-colors"
              >
                Review extraction
              </Link>
            </div>
          )}
        </section>
      )}

      {/* Timestamps */}
      <section>
        <h2 className="text-sm font-medium mb-2">Timestamps</h2>
        <dl className="text-xs space-y-1">
          <Row label="Created" value={String(run.created_at)} />
          <Row label="Updated" value={String(run.updated_at)} />
        </dl>
      </section>
    </div>
  );
}

function StatusBadge({ label, value }: { label: string; value: string }) {
  const color =
    value === "completed"
      ? "bg-green-100 text-green-700"
      : value === "failed" || value === "error"
        ? "bg-red-100 text-red-700"
        : "bg-yellow-100 text-yellow-700";

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-500">{label}</span>
      <span className={`text-xs px-2 py-0.5 rounded font-medium ${color}`}>
        {value}
      </span>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <dt className="text-gray-500 w-32 shrink-0">{label}</dt>
      <dd className="font-mono break-all">{value}</dd>
    </div>
  );
}
