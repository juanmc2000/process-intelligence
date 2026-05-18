"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ProcessSummaryResponse } from "@/lib/api";

const SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".eml", ".zip", ".txt", ".md"];

function isSupportedFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return SUPPORTED_EXTENSIONS.some((ext) => name.endsWith(ext));
}

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function IconUploadCloud() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="w-9 h-9">
      <polyline points="16 16 12 12 8 16" />
      <line x1="12" y1="12" x2="12" y2="21" />
      <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3" />
    </svg>
  );
}

function IconConnect() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="w-9 h-9">
      <circle cx="18" cy="18" r="3" />
      <circle cx="6" cy="6" r="3" />
      <circle cx="6" cy="18" r="3" />
      <line x1="6" y1="9" x2="6" y2="15" />
      <path d="M13 6h3a2 2 0 0 1 2 2v7" />
    </svg>
  );
}

function IconClock() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

function IconLayers() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5">
      <polygon points="12 2 2 7 12 12 22 7 12 2" />
      <polyline points="2 17 12 22 22 17" />
      <polyline points="2 12 12 17 22 12" />
    </svg>
  );
}

function IconSearch() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

function IconBell() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}

function IconHelp() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <circle cx="12" cy="12" r="10" />
      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Workflow card
// ---------------------------------------------------------------------------

function WorkflowCard({ process }: { process: ProcessSummaryResponse }) {
  const name = process.filename ?? "Untitled workflow";
  const id = process.extraction_result_id;

  return (
    <div className="card p-4 flex flex-col gap-3 min-w-0">
      <div className="flex items-start justify-between gap-2">
        <span className="text-[14px] font-semibold text-[var(--text-primary)] leading-snug line-clamp-2">
          {name}
        </span>
        <span className="text-[10px] text-[var(--text-muted)] italic shrink-0 mt-0.5">
          No score yet
        </span>
      </div>

      <div className="flex items-center gap-1.5 text-[11px] text-[var(--text-muted)]">
        <span className="flex items-center gap-1">
          <IconLayers />
          <span className="italic">Uncategorised</span>
        </span>
      </div>

      <div className="flex items-center justify-between border-t border-[var(--border-soft)] pt-2.5 mt-auto">
        <Link
          href={`/processes/${id}`}
          className="text-[12px] font-semibold text-accent hover:text-accent-hover transition-colors"
        >
          Review narrative
        </Link>
        <div className="flex items-center gap-1 text-[11px] text-[var(--text-muted)] italic">
          <IconClock />
          <span>Date not available</span>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Recent activity item
// ---------------------------------------------------------------------------

function ActivityItem({
  label,
  when,
  color,
}: {
  label: string;
  when: string;
  color: string;
}) {
  return (
    <div className="flex items-center gap-3 py-2">
      <div className={`w-2 h-2 rounded-full shrink-0 ${color}`} />
      <div className="flex-1 min-w-0">
        <div className="text-[13px] font-medium text-[var(--text-primary)] truncate">{label}</div>
        <div className="text-[11px] text-[var(--text-muted)]">{when}</div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function Home() {
  const router = useRouter();
  const [processes, setProcesses] = useState<ProcessSummaryResponse[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [skippedCount, setSkippedCount] = useState(0);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dirInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.listProcesses({ limit: 3 }).then(setProcesses).catch(() => {});
  }, []);

  // Set webkitdirectory on the directory input — not in React's type defs
  useEffect(() => {
    if (dirInputRef.current) {
      dirInputRef.current.setAttribute("webkitdirectory", "");
      dirInputRef.current.setAttribute("multiple", "");
    }
  }, []);

  async function handleFiles(files: File[]) {
    setUploadError(null);
    const supported = files.filter(isSupportedFile);
    const skipped = files.length - supported.length;
    setSkippedCount(skipped);

    if (supported.length === 0) {
      setUploadError("No supported files selected (PDF, EML, ZIP, TXT, MD).");
      return;
    }

    setUploading(true);
    try {
      const res =
        supported.length === 1
          ? await api.upload(supported[0])
          : await api.uploadMultiple(supported);
      router.push(`/runs/${res.run_id}`);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
      setUploading(false);
    }
  }

  function onDragOver(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(true);
  }

  function onDragLeave(e: React.DragEvent) {
    // Only clear if leaving the card itself, not a child element
    if (!e.currentTarget.contains(e.relatedTarget as Node)) {
      setDragOver(false);
    }
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) handleFiles(files);
  }

  function onFileInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    if (files.length > 0) handleFiles(files);
    e.target.value = "";
  }

  const recentActivity = [
    { label: "Deposit Processing Workflow", when: "Updated 2h ago", color: "bg-emerald-500" },
    { label: "Vendor Onboarding Process", when: "Updated 6h ago", color: "bg-amber-400" },
    { label: "Loan Disbursement Workflow", when: "Updated 1d ago", color: "bg-emerald-500" },
    { label: "Customer Refund Process", when: "Updated 1d ago", color: "bg-emerald-500" },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Top bar */}
      <div className="px-8 py-4 flex items-center gap-4 border-b border-[var(--border-soft)] bg-white">
        <div className="flex-1 flex items-center gap-2 bg-[var(--surface-soft)] border border-[var(--border-soft)] rounded-lg px-3 py-2 text-[13px] text-[var(--text-muted)]">
          <IconSearch />
          <span>Search workflows, sources, or tasks…</span>
          <span className="ml-auto text-[11px] bg-[var(--surface-muted)] border border-[var(--border-strong)] rounded px-1.5 py-0.5 font-mono tracking-wider">
            ⌘K
          </span>
        </div>
        <button className="text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors relative">
          <IconBell />
        </button>
        <button className="text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors">
          <IconHelp />
        </button>
        <div
          className="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-semibold shrink-0"
          style={{ background: "var(--accent)" }}
        >
          U
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-8 py-8">
        {/* Greeting */}
        <div className="mb-8">
          <h1 className="text-[28px] font-bold text-[var(--text-primary)] leading-tight">
            Good morning 👋
          </h1>
          <p className="text-[14px] text-[var(--text-secondary)] mt-1">
            Understand your workflows before you automate them.
          </p>
        </div>

        {/* Action cards + Recent activity */}
        <div className="flex gap-6 mb-10">
          {/* Upload card — drag-and-drop zone (UI-019), file picker (UI-020), folder picker (UI-021) */}
          <div
            className={`card p-6 flex-1 flex flex-col items-center text-center gap-4 min-w-0 transition-colors ${
              dragOver ? "border-[var(--accent)] bg-[var(--surface-soft)]" : ""
            }`}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
          >
            <div className="text-[var(--accent)] transition-opacity">
              <IconUploadCloud />
            </div>
            <div>
              <div className="text-[15px] font-semibold text-[var(--text-primary)] mb-1">
                Upload operational artifacts
              </div>
              <div className="text-[12px] text-[var(--text-muted)] leading-relaxed">
                {dragOver ? (
                  <span className="text-[var(--accent)] font-medium">Drop files here</span>
                ) : (
                  <>Drag &amp; drop or browse<br />PDF, DOCX, EML, ZIP, TXT, MD</>
                )}
              </div>
            </div>

            <div className="mt-auto flex flex-col items-center gap-2">
              {uploading ? (
                <span className="text-[13px] text-[var(--text-muted)] animate-pulse">Uploading…</span>
              ) : (
                <>
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="inline-flex items-center justify-center px-5 py-2 rounded-btn text-[13px] font-semibold text-white transition-colors"
                    style={{ background: "var(--accent)" }}
                  >
                    Upload files
                  </button>
                  <button
                    onClick={() => dirInputRef.current?.click()}
                    className="text-[12px] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
                  >
                    Or choose a folder
                  </button>
                </>
              )}
              {uploadError && (
                <p className="text-[11px] text-red-500 mt-1">{uploadError}</p>
              )}
              {skippedCount > 0 && !uploadError && (
                <p className="text-[11px] text-[var(--text-muted)]">
                  {skippedCount} unsupported file{skippedCount > 1 ? "s" : ""} skipped
                </p>
              )}
            </div>

            {/* Hidden file inputs */}
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.eml,.zip,.txt,.md"
              multiple
              className="hidden"
              onChange={onFileInputChange}
            />
            <input
              ref={dirInputRef}
              type="file"
              className="hidden"
              onChange={onFileInputChange}
            />
          </div>

          {/* Connect source card */}
          <div className="card p-6 flex-1 flex flex-col items-center text-center gap-4 min-w-0 opacity-60">
            <div className="text-[var(--text-secondary)]">
              <IconConnect />
            </div>
            <div>
              <div className="text-[15px] font-semibold text-[var(--text-primary)] mb-1">
                Connect approved source
              </div>
              <div className="text-[12px] text-[var(--text-muted)] leading-relaxed">
                Slack, Teams, SharePoint, Email,<br />
                Jira, Confluence + more
              </div>
            </div>
            <button
              disabled
              title="Coming soon"
              className="mt-auto inline-flex items-center justify-center px-5 py-2 rounded-btn text-[13px] font-semibold border border-[var(--border-soft)] text-[var(--text-muted)] cursor-not-allowed"
            >
              Coming soon
            </button>
          </div>

          {/* Recent activity */}
          <div className="card p-5 w-64 shrink-0 flex flex-col">
            <div className="flex items-center justify-between mb-1">
              <h2 className="text-[13px] font-semibold text-[var(--text-primary)]">Recent activity</h2>
              <span className="text-[10px] text-[var(--text-muted)] italic">Demo data</span>
            </div>
            <div className="divide-y divide-[var(--border-soft)] flex-1">
              {recentActivity.map((a) => (
                <ActivityItem key={a.label} {...a} />
              ))}
            </div>
            <Link
              href="/processes"
              className="text-[12px] text-accent font-medium mt-3 hover:text-accent-hover transition-colors"
            >
              View all activity →
            </Link>
          </div>
        </div>

        {/* Recent workflow reconstructions */}
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-[17px] font-semibold text-[var(--text-primary)]">
            Recent workflow reconstructions
          </h2>
          <Link href="/processes" className="text-[13px] text-accent font-medium hover:text-accent-hover transition-colors">
            View all
          </Link>
        </div>

        {processes.length > 0 ? (
          <div className="grid grid-cols-3 gap-4">
            {processes.map((p) => (
              <WorkflowCard key={p.extraction_result_id} process={p} />
            ))}
          </div>
        ) : (
          <div className="card p-8 text-center">
            <p className="text-[14px] text-[var(--text-muted)]">
              No workflows yet. Upload an artifact to get started.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
