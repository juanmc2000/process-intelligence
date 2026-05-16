"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, ProcessDetailResponse, RunDetailResponse, SourceResponse } from "@/lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Tab = "narrative" | "workflow" | "sources" | "insights" | "activity";

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function IconShare() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
      <circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" />
      <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" /><line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
    </svg>
  );
}

function IconExport() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}

function IconChevronRight() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5">
      <polyline points="9 18 15 12 9 6" />
    </svg>
  );
}

function IconAlertTriangle() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5">
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

function IconCheckCircle() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Confidence ring SVG
// ---------------------------------------------------------------------------

function ConfidenceRing({ score }: { score: number }) {
  const r = 28;
  const circ = 2 * Math.PI * r;
  const offset = circ - (score / 100) * circ;
  const color = score >= 75 ? "#10B981" : score >= 50 ? "#F59E0B" : "#EF4444";
  const label = score >= 75 ? "High confidence" : score >= 50 ? "Medium confidence" : "Low confidence";

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative w-20 h-20">
        <svg className="w-20 h-20 -rotate-90" viewBox="0 0 72 72">
          <circle cx="36" cy="36" r={r} fill="none" stroke="#E4E8F0" strokeWidth="6" />
          <circle
            cx="36" cy="36" r={r} fill="none"
            stroke={color} strokeWidth="6"
            strokeDasharray={circ}
            strokeDashoffset={offset}
            strokeLinecap="round"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-[18px] font-bold" style={{ color }}>{score}%</span>
        </div>
      </div>
      <span className="text-[12px] font-semibold" style={{ color }}>{label}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers: derive narrative content from ProcessIR
// ---------------------------------------------------------------------------

function deriveWorkflowName(data: ProcessDetailResponse): string {
  const ir = data.process_ir as Record<string, unknown> | null;
  if (ir?.process_name && typeof ir.process_name === "string") return ir.process_name;
  return "Workflow";
}

function deriveSummary(ir: Record<string, unknown>): string {
  const steps = (ir.workflow_steps as unknown[]) ?? [];
  const roles = (ir.roles as unknown[]) ?? [];
  const systems = (ir.system_touchpoints as unknown[]) ?? [];
  const controls = (ir.controls as unknown[]) ?? [];

  const stepCount = steps.length;
  const roleList = roles
    .slice(0, 3)
    .map((r) => String((r as Record<string, unknown>).name ?? ""))
    .filter(Boolean)
    .join(", ");
  const systemList = systems
    .slice(0, 3)
    .map((s) => String((s as Record<string, unknown>).system_name ?? ""))
    .filter(Boolean)
    .join(", ");

  let summary = `This workflow describes the operational process`;
  if (stepCount > 0) summary += ` across ${stepCount} steps`;
  if (roleList) summary += `, involving ${roleList}`;
  if (systemList) summary += ` and touching systems including ${systemList}`;
  summary += ".";
  if (controls.length > 0)
    summary += ` ${controls.length} control${controls.length !== 1 ? "s" : ""} have been identified to govern this process.`;
  return summary;
}

function deriveFindings(ir: Record<string, unknown>): string[] {
  const findings: string[] = [];
  const controls = (ir.controls as Array<Record<string, unknown>>) ?? [];
  const exceptions = (ir.exception_flows as Array<Record<string, unknown>>) ?? [];
  const decisions = (ir.decision_point_count as number) ?? 0;
  const changes = (ir.change_events as Array<Record<string, unknown>>) ?? [];

  controls.slice(0, 2).forEach((c) => {
    const name = String(c.name ?? "");
    if (name) findings.push(`Control identified: ${name}`);
  });
  if (exceptions.length > 0)
    findings.push(`${exceptions.length} exception path${exceptions.length !== 1 ? "s" : ""} documented in this workflow`);
  if (decisions > 0)
    findings.push(`${decisions} decision point${decisions !== 1 ? "s" : ""} requiring approval or routing logic`);
  changes.slice(0, 1).forEach((e) => {
    const name = String(e.name ?? "");
    if (name) findings.push(`Change event recorded: ${name}`);
  });

  if (findings.length === 0)
    findings.push("Workflow structure extracted — review steps for accuracy");

  return findings;
}

function deriveConfidenceScore(summary: Record<string, number> | null): number {
  if (!summary) return 0;
  const populated = Object.values(summary).filter((v) => v > 0).length;
  const total = Object.keys(summary).length || 1;
  return Math.round(50 + (populated / total) * 40);
}

// ---------------------------------------------------------------------------
// Sources tab helpers
// ---------------------------------------------------------------------------

function formatBytes(bytes: number | null): string {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

function sourceTypeBadge(contentType: string | null): string {
  if (!contentType) return "Unknown";
  if (contentType.includes("pdf")) return "PDF";
  if (contentType.includes("email") || contentType.includes("message/rfc")) return "Email";
  if (contentType.includes("zip")) return "ZIP";
  if (contentType.includes("word") || contentType.includes("docx")) return "DOCX";
  if (contentType.includes("csv")) return "CSV";
  if (contentType.includes("plain")) return "Text";
  if (contentType.includes("image")) return "Image";
  const ext = contentType.split("/").pop()?.toUpperCase() ?? "File";
  return ext;
}

function SourceCard({ source }: { source: SourceResponse }) {
  const typeLabel = sourceTypeBadge(source.content_type);
  const statusColor =
    source.status === "parsed" || source.status === "completed"
      ? "text-emerald-600 bg-emerald-50 border-emerald-200"
      : source.status === "failed"
      ? "text-red-600 bg-red-50 border-red-200"
      : "text-[var(--text-muted)] bg-[var(--surface-soft)] border-[var(--border-soft)]";

  return (
    <div className="card p-4 flex flex-col gap-2.5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <span
            className="px-2 py-0.5 rounded text-[11px] font-semibold border shrink-0"
            style={{ color: "var(--accent)", background: "var(--accent-soft)", borderColor: "var(--accent-soft)" }}
          >
            {typeLabel}
          </span>
          <span className="text-[13px] font-medium text-[var(--text-primary)] truncate">
            {source.filename || "Untitled source"}
          </span>
        </div>
        <span className={`text-[10px] font-medium px-2 py-0.5 rounded border shrink-0 ${statusColor}`}>
          {source.status}
        </span>
      </div>

      <div className="flex items-center gap-4 text-[11px] text-[var(--text-muted)]">
        <span>{formatBytes(source.size_bytes)}</span>
        <span>Ingested {formatDate(source.created_at)}</span>
      </div>

      {source.input_hash && (
        <div className="text-[10px] text-[var(--text-muted)] font-mono truncate">
          Hash: {source.input_hash.slice(0, 16)}…
        </div>
      )}
    </div>
  );
}

function SourcesTab({ runDetail, loadingRun }: { runDetail: RunDetailResponse | null; loadingRun: boolean }) {
  if (loadingRun) {
    return (
      <div className="flex items-center justify-center h-40 text-[var(--text-muted)] text-[13px]">
        Loading sources…
      </div>
    );
  }

  if (!runDetail) {
    return (
      <div className="flex items-center justify-center h-40 text-[var(--text-muted)] text-[13px] italic">
        Source data not available.
      </div>
    );
  }

  const { sources, artifacts } = runDetail;

  // Group artifacts by source id for provenance chips
  const artifactsBySourceId = new Map<string, string[]>();
  for (const a of artifacts) {
    // artifact object_uri encodes source; we show artifact_type as provenance
    const sid = "run"; // artifacts are run-level in current schema
    if (!artifactsBySourceId.has(sid)) artifactsBySourceId.set(sid, []);
    const types = artifactsBySourceId.get(sid)!;
    if (!types.includes(a.artifact_type)) types.push(a.artifact_type);
  }

  const artifactTypes = [...new Set(artifacts.map((a) => a.artifact_type))];

  return (
    <div className="px-8 py-8 max-w-4xl space-y-6">
      {/* Summary row */}
      <div className="flex items-center gap-6 text-[13px] text-[var(--text-secondary)]">
        <span>
          <strong className="text-[var(--text-primary)]">{sources.length}</strong> source file{sources.length !== 1 ? "s" : ""}
        </span>
        <span>
          <strong className="text-[var(--text-primary)]">{artifacts.length}</strong> artifact{artifacts.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Provenance chips */}
      {artifactTypes.length > 0 && (
        <div>
          <h3 className="text-[12px] font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-2">
            Extraction provenance
          </h3>
          <div className="flex flex-wrap gap-2">
            {artifactTypes.map((t) => (
              <span
                key={t}
                className="px-2.5 py-1 text-[11px] font-medium rounded-full border"
                style={{ color: "var(--text-secondary)", borderColor: "var(--border-strong)", background: "var(--surface-soft)" }}
              >
                {t.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Source cards */}
      {sources.length === 0 ? (
        <div className="card p-6 text-center text-[13px] text-[var(--text-muted)] italic">
          No source files recorded for this run.
        </div>
      ) : (
        <div>
          <h3 className="text-[12px] font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-3">
            Source files
          </h3>
          <div className="space-y-3">
            {sources.map((s) => (
              <SourceCard key={s.id} source={s} />
            ))}
          </div>
        </div>
      )}

      {/* Artifact metadata */}
      {artifacts.length > 0 && (
        <div>
          <h3 className="text-[12px] font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-3">
            Extraction artifacts
          </h3>
          <div className="space-y-2">
            {artifacts.map((a) => (
              <div key={a.id} className="card p-3 flex items-center justify-between gap-4">
                <div className="flex items-center gap-3 min-w-0">
                  <span
                    className="px-2 py-0.5 rounded text-[11px] font-semibold border shrink-0"
                    style={{ color: "var(--text-secondary)", borderColor: "var(--border-strong)", background: "var(--surface-soft)" }}
                  >
                    {a.artifact_type.replace(/_/g, " ")}
                  </span>
                  <span className="text-[12px] text-[var(--text-muted)] truncate">
                    {formatBytes(a.size_bytes)} · {formatDate(a.created_at)}
                  </span>
                </div>
                <span className={`text-[10px] font-medium px-2 py-0.5 rounded border shrink-0 ${a.deletion_eligible ? "text-amber-600 bg-amber-50 border-amber-200" : "text-emerald-600 bg-emerald-50 border-emerald-200"}`}>
                  {a.deletion_eligible ? "Temporary" : "Durable"}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <p className="text-[11px] text-[var(--text-muted)] italic">
        Source metadata only — no raw document content is stored or displayed.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

const TABS: { key: Tab; label: string }[] = [
  { key: "narrative", label: "Narrative" },
  { key: "workflow", label: "Workflow" },
  { key: "sources", label: "Sources" },
  { key: "insights", label: "Insights" },
  { key: "activity", label: "Activity" },
];

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function WorkflowNarrativePage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<ProcessDetailResponse | null>(null);
  const [runDetail, setRunDetail] = useState<RunDetailResponse | null>(null);
  const [loadingRun, setLoadingRun] = useState(false);
  const [tab, setTab] = useState<Tab>("narrative");

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    api.getProcess(id).then((d) => {
      if (!cancelled) {
        setData(d);
        setLoading(false);
        // Fetch run detail for Sources tab
        setLoadingRun(true);
        api.getRun(d.run_id).then((r) => {
          if (!cancelled) { setRunDetail(r); setLoadingRun(false); }
        }).catch(() => {
          if (!cancelled) setLoadingRun(false);
        });
      }
    }).catch((e) => {
      if (!cancelled) { setError(e instanceof Error ? e.message : "Failed to load"); setLoading(false); }
    });
    return () => { cancelled = true; };
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-[var(--text-muted)] text-sm">
        Loading workflow…
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="card p-4 text-sm" style={{ color: "var(--danger)", borderColor: "var(--danger)" }}>
          {error}
        </div>
      </div>
    );
  }

  if (!data) return null;

  const ir = data.process_ir as Record<string, unknown> | null;
  const summary = data.confidence_summary;
  const workflowName = deriveWorkflowName(data);
  const confidenceScore = deriveConfidenceScore(summary);
  const narrativeSummary = ir ? deriveSummary(ir) : "No ProcessIR data available.";
  const findings = ir ? deriveFindings(ir) : [];

  const atAGlance = [
    { label: "Steps", value: summary?.workflow_step_count ?? 0 },
    { label: "Roles", value: summary?.role_count ?? 0 },
    { label: "Systems", value: summary?.system_touchpoint_count ?? 0 },
    { label: "Controls", value: summary?.control_count ?? 0 },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Dark top banner */}
      <div
        className="shrink-0 header-divider"
        style={{ background: "var(--navy-850)" }}
      >
        {/* Breadcrumb + actions row */}
        <div className="px-8 pt-5 pb-0 flex items-center justify-between gap-4">
          <div className="flex items-center gap-1.5 text-[12px] text-white/40">
            <Link href="/processes" className="hover:text-white/70 transition-colors">Workflows</Link>
            <IconChevronRight />
            <span className="text-white/70 truncate max-w-[200px]">{workflowName}</span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button disabled title="Coming soon" className="flex items-center gap-1.5 px-3 py-1.5 rounded-btn text-[12px] font-medium text-white/30 border border-white/8 cursor-not-allowed">
              <IconShare />
              Share
            </button>
            <button disabled title="Coming soon" className="flex items-center gap-1.5 px-3 py-1.5 rounded-btn text-[12px] font-medium text-white/30 border border-white/8 cursor-not-allowed">
              <IconExport />
              Export
            </button>
            <Link
              href={`/processes/${id}/graph`}
              className="flex items-center gap-1.5 px-4 py-1.5 rounded-btn text-[12px] font-semibold text-white transition-colors"
              style={{ background: "var(--accent)" }}
            >
              Explore workflow
            </Link>
          </div>
        </div>

        {/* Title + meta + confidence */}
        <div className="px-8 py-4 flex items-end justify-between gap-6">
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-1.5">
              <h1 className="text-[22px] font-bold text-white leading-tight truncate">
                {workflowName}
              </h1>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-white/10 text-white/60 border border-white/15 shrink-0">
                Draft
              </span>
            </div>
            <div className="flex items-center gap-4 text-[11px] text-white/40">
              <span className="italic">Last updated: not available</span>
            </div>
          </div>
          <div className="shrink-0">
            <ConfidenceRing score={confidenceScore} />
          </div>
        </div>

        {/* Tab strip */}
        <div className="px-8 flex items-end gap-1 border-t border-white/5 mt-1">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={[
                "px-4 py-2.5 text-[13px] font-medium border-b-2 transition-colors",
                tab === t.key
                  ? "border-white text-white"
                  : "border-transparent text-white/45 hover:text-white/70",
              ].join(" ")}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto bg-[var(--surface-soft)]">
        {tab === "narrative" && (
          <div className="flex gap-6 px-8 py-8 max-w-6xl">
            {/* Left: narrative */}
            <div className="flex-1 min-w-0 space-y-8">
              <section>
                <h2 className="text-[17px] font-semibold text-[var(--text-primary)] mb-3">
                  Workflow summary
                </h2>
                <p className="text-[14px] text-[var(--text-secondary)] leading-relaxed">
                  {narrativeSummary}
                </p>
                <button
                  onClick={() => setTab("sources")}
                  className="mt-3 text-[12px] text-accent font-medium hover:text-accent-hover transition-colors"
                >
                  View sources →
                </button>
              </section>

              {findings.length > 0 && (
                <section>
                  <h2 className="text-[17px] font-semibold text-[var(--text-primary)] mb-3">
                    Key findings
                  </h2>
                  <ol className="space-y-3">
                    {findings.map((f, i) => (
                      <li key={i} className="flex gap-3">
                        <span
                          className="w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-bold shrink-0 mt-0.5"
                          style={{ background: "var(--accent-soft)", color: "var(--accent)" }}
                        >
                          {i + 1}
                        </span>
                        <p className="text-[13px] text-[var(--text-secondary)] leading-relaxed">{f}</p>
                      </li>
                    ))}
                  </ol>
                </section>
              )}
            </div>

            {/* Right: at-a-glance + confidence + notes */}
            <div className="w-64 shrink-0 space-y-4">
              {/* At a glance */}
              <div className="card p-4">
                <h3 className="text-[12px] font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-3">
                  At a glance
                </h3>
                <div className="space-y-2.5">
                  {atAGlance.map(({ label, value }) => (
                    <div key={label} className="flex items-center justify-between">
                      <span className="text-[13px] text-[var(--text-secondary)]">{label}</span>
                      <span className="text-[13px] font-semibold text-[var(--text-primary)]">{value}</span>
                    </div>
                  ))}
                </div>
                <button
                  onClick={() => setTab("sources")}
                  className="mt-3 text-[12px] text-accent font-medium hover:text-accent-hover transition-colors"
                >
                  View sources →
                </button>
              </div>

              {/* Confidence */}
              <div className="card p-4 flex flex-col items-center text-center gap-3">
                <h3 className="text-[12px] font-semibold text-[var(--text-muted)] uppercase tracking-wide self-start">
                  Confidence
                </h3>
                <ConfidenceRing score={confidenceScore} />
                <p className="text-[11px] text-[var(--text-muted)]">
                  Based on {Object.values(summary ?? {}).reduce((a, b) => a + b, 0)} data points
                </p>
                <button className="text-[11px] text-accent font-medium hover:text-accent-hover transition-colors">
                  How confidence works
                </button>
              </div>

              {/* Unresolved ambiguities */}
              {ir && (
                <div className="card p-4">
                  <h3 className="text-[12px] font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-3">
                    Unresolved ambiguities
                  </h3>
                  <div className="space-y-2">
                    {(ir.exception_flows as unknown[] ?? []).slice(0, 2).length > 0 ? (
                      (ir.exception_flows as Array<Record<string, unknown>>).slice(0, 2).map((e, i) => (
                        <div key={i} className="flex items-start gap-2 text-[12px] text-[var(--text-secondary)]">
                          <span className="text-amber-500 mt-0.5"><IconAlertTriangle /></span>
                          <span>{String(e.condition ?? e.name ?? "Exception path not fully defined")}</span>
                        </div>
                      ))
                    ) : (
                      <div className="flex items-start gap-2 text-[12px] text-[var(--text-muted)]">
                        <span className="text-emerald-500 mt-0.5"><IconCheckCircle /></span>
                        <span>No critical ambiguities detected</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Recommended next steps */}
              <div className="card p-4">
                <h3 className="text-[12px] font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-3">
                  Recommended next steps
                </h3>
                <div className="space-y-2 text-[12px] text-[var(--text-secondary)]">
                  <div className="flex items-start gap-2">
                    <span className="text-emerald-500 mt-0.5"><IconCheckCircle /></span>
                    <span>Review and validate extracted workflow steps</span>
                  </div>
                  <div className="flex items-start gap-2">
                    <span className="text-emerald-500 mt-0.5"><IconCheckCircle /></span>
                    <span>Standardize terminology across departments</span>
                  </div>
                  <div className="flex items-start gap-2">
                    <span className="text-emerald-500 mt-0.5"><IconCheckCircle /></span>
                    <span>
                      <Link href={`/processes/${id}/graph`} className="text-accent hover:text-accent-hover font-medium">
                        Explore workflow graph
                      </Link>{" "}
                      to verify structure
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {tab === "workflow" && (
          <div className="flex flex-col items-center justify-center h-full gap-4 text-[var(--text-muted)]">
            <p className="text-[14px]">Visualise the workflow structure in the graph view.</p>
            <Link
              href={`/processes/${id}/graph`}
              className="px-5 py-2 rounded-btn text-[13px] font-semibold text-white transition-colors"
              style={{ background: "var(--accent)" }}
            >
              Open workflow graph
            </Link>
          </div>
        )}

        {tab === "sources" && (
          <SourcesTab runDetail={runDetail} loadingRun={loadingRun} />
        )}

        {(tab === "insights" || tab === "activity") && (
          <div className="flex items-center justify-center h-full text-[var(--text-muted)] text-[14px] italic">
            {tab.charAt(0).toUpperCase() + tab.slice(1)} — coming soon
          </div>
        )}
      </div>
    </div>
  );
}
