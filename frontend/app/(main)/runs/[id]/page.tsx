"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, RunDetailResponse } from "@/lib/api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function friendlyFileType(contentType: string | null, filename: string): string {
  if (contentType) {
    if (contentType.includes("pdf")) return "PDF";
    if (contentType.includes("wordprocessingml") || contentType.includes("docx")) return "DOCX";
    if (contentType.includes("zip")) return "ZIP";
    if (contentType.includes("text/plain")) return "TXT";
    if (contentType.includes("message/rfc822")) return "EML";
    if (contentType.includes("markdown")) return "MD";
  }
  const ext = filename.split(".").pop()?.toUpperCase();
  return ext ?? "FILE";
}

function formatBytes(bytes: number | null): string {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

function StatusBadge({ value }: { value: string }) {
  const cfg =
    value === "completed"
      ? { cls: "bg-emerald-100 text-emerald-700", label: "Completed" }
      : value === "failed"
      ? { cls: "bg-red-100 text-red-600", label: "Failed" }
      : value === "error"
      ? { cls: "bg-red-100 text-red-600", label: "Error" }
      : value === "parsed"
      ? { cls: "bg-sky-100 text-sky-700", label: "Parsed" }
      : value === "uploaded"
      ? { cls: "bg-blue-100 text-blue-700", label: "Uploaded" }
      : { cls: "bg-amber-100 text-amber-700", label: value };

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-semibold ${cfg.cls}`}
    >
      {cfg.label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Meta row
// ---------------------------------------------------------------------------

function MetaRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-4 py-1.5">
      <span className="text-[12px] text-[var(--text-muted)] w-32 shrink-0">{label}</span>
      <div>{children}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section heading
// ---------------------------------------------------------------------------

function SectionHeading({ title, count }: { title: string; count?: number }) {
  return (
    <div className="flex items-center gap-2 mb-5">
      <h2 className="text-[15px] font-semibold text-[var(--text-primary)]">{title}</h2>
      {count != null && (
        <span className="text-[12px] text-[var(--text-muted)]">({count})</span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

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
    const interval = setInterval(async () => {
      const data = await api.getRun(runId).catch(() => null);
      if (!data) return;
      setRun(data);
      if (["completed", "failed", "error"].includes(data.status)) {
        clearInterval(interval);
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [runId, load]);

  if (error) {
    return (
      <div className="px-8 py-8">
        <p className="text-[13px]" style={{ color: "var(--danger)" }}>{error}</p>
      </div>
    );
  }

  if (!run) {
    return (
      <div className="px-8 py-8">
        <p className="text-[13px] text-[var(--text-muted)]">Loading…</p>
      </div>
    );
  }

  const extractionDone =
    run.extraction?.status === "completed" && run.extraction.process_ir_uri;

  return (
    <div className="flex flex-col h-full">
      {/* Top bar */}
      <div className="px-8 py-5 bg-white border-b border-[var(--border-soft)] header-divider flex items-start justify-between gap-6">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 text-[12px] text-[var(--text-muted)] mb-1.5">
            <Link
              href="/runs/upload"
              className="hover:text-[var(--text-primary)] transition-colors"
            >
              Uploads
            </Link>
            <span>/</span>
            <span className="text-[var(--text-secondary)]">Run detail</span>
          </div>
          <h1 className="text-[22px] font-bold text-[var(--text-primary)] leading-tight">
            Run detail
          </h1>
          <p className="text-[11px] font-mono text-[var(--text-muted)] mt-0.5 truncate max-w-lg">
            {run.id}
          </p>
        </div>

        {/* Status badges */}
        <div className="flex items-center gap-2 shrink-0 pt-1">
          <span className="text-[12px] text-[var(--text-muted)]">Run</span>
          <StatusBadge value={run.status} />
          {run.extraction && (
            <>
              <span className="text-[var(--border-strong)]">·</span>
              <span className="text-[12px] text-[var(--text-muted)]">Extraction</span>
              <StatusBadge value={run.extraction.status} />
            </>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-8 py-8 space-y-5">
        {/* Error message */}
        {run.error_message && (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-700">
            {run.error_message}
          </div>
        )}

        {/* Sources */}
        {run.sources.length > 0 && (
          <div className="card p-6">
            <SectionHeading title="Sources" count={run.sources.length} />
            <div>
              {run.sources.map((s) => (
                <div
                  key={s.id}
                  className="flex items-center gap-4 py-3 border-b border-[var(--border-soft)] last:border-0"
                >
                  <span className="flex-1 min-w-0 text-[13px] font-medium text-[var(--text-primary)] font-mono truncate">
                    {s.filename}
                  </span>
                  <span className="text-[11px] font-semibold text-[var(--text-secondary)] bg-[var(--surface-muted)] border border-[var(--border-soft)] rounded-md px-2 py-0.5 shrink-0">
                    {friendlyFileType(s.content_type, s.filename)}
                  </span>
                  <span className="text-[12px] text-[var(--text-muted)] w-16 text-right shrink-0 tabular-nums">
                    {formatBytes(s.size_bytes)}
                  </span>
                  <div className="shrink-0">
                    <StatusBadge value={s.status} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Extraction */}
        {run.extraction && (
          <div className="card p-6">
            <SectionHeading title="Extraction" />
            <div className="space-y-0.5 mb-6">
              <MetaRow label="Status">
                <StatusBadge value={run.extraction.status} />
              </MetaRow>
              <MetaRow label="Schema version">
                <span className="text-[13px] font-mono text-[var(--text-secondary)]">
                  {run.extraction.schema_version ?? "—"}
                </span>
              </MetaRow>
            </div>
            {extractionDone && (
              <Link
                href={`/runs/${runId}/review`}
                className="inline-flex items-center justify-center px-5 py-2 rounded-btn text-[13px] font-semibold text-white transition-colors"
                style={{ background: "var(--accent)" }}
              >
                Review extraction
              </Link>
            )}
            {!extractionDone && run.extraction.status !== "completed" && (
              <p className="text-[12px] text-[var(--text-muted)] italic">
                Processing — review will be available once extraction completes.
              </p>
            )}
          </div>
        )}

        {/* Timeline */}
        <div className="card p-6">
          <SectionHeading title="Timeline" />
          <div className="space-y-0.5">
            <MetaRow label="Created">
              <span className="text-[13px] text-[var(--text-secondary)]">
                {formatDate(run.created_at)}
              </span>
            </MetaRow>
            <MetaRow label="Last updated">
              <span className="text-[13px] text-[var(--text-secondary)]">
                {formatDate(run.updated_at)}
              </span>
            </MetaRow>
          </div>
        </div>
      </div>
    </div>
  );
}
