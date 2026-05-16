"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface StatusRow {
  label: string;
  status: "checking" | "ok" | "error";
  detail?: string;
}

/**
 * Health check screen — probes /health and /ready on the backend API.
 * Displays connectivity status and the API base URL.
 */
export default function HealthPage() {
  const [rows, setRows] = useState<StatusRow[]>([
    { label: "/health", status: "checking" },
    { label: "/ready", status: "checking" },
  ]);

  useEffect(() => {
    const probe = async (
      index: number,
      fn: () => Promise<{ status: string }>
    ) => {
      try {
        const res = await fn();
        setRows((prev) =>
          prev.map((r, i) =>
            i === index ? { ...r, status: "ok", detail: res.status } : r
          )
        );
      } catch (err) {
        setRows((prev) =>
          prev.map((r, i) =>
            i === index
              ? {
                  ...r,
                  status: "error",
                  detail: err instanceof Error ? err.message : "unreachable",
                }
              : r
          )
        );
      }
    };

    probe(0, () => api.health());
    probe(1, () => api.ready());
  }, []);

  const badge = (status: StatusRow["status"]) => {
    if (status === "checking")
      return (
        <span className="text-gray-400 text-xs font-mono">checking…</span>
      );
    if (status === "ok")
      return (
        <span className="text-green-600 text-xs font-mono font-semibold">
          ✓ ok
        </span>
      );
    return (
      <span className="text-red-600 text-xs font-mono font-semibold">
        ✗ error
      </span>
    );
  };

  const apiUrl =
    process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8010 (default)";

  return (
    <div className="max-w-lg">
      <h1 className="text-xl font-semibold mb-1">API Health</h1>
      <p className="text-xs text-gray-500 mb-6 font-mono">{apiUrl}</p>

      <table className="w-full text-sm border border-gray-200 rounded overflow-hidden">
        <thead className="bg-gray-100">
          <tr>
            <th className="text-left px-4 py-2 font-medium">Endpoint</th>
            <th className="text-left px-4 py-2 font-medium">Status</th>
            <th className="text-left px-4 py-2 font-medium">Detail</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label} className="border-t border-gray-200">
              <td className="px-4 py-2 font-mono text-xs">{row.label}</td>
              <td className="px-4 py-2">{badge(row.status)}</td>
              <td className="px-4 py-2 text-gray-500 text-xs">
                {row.detail ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
