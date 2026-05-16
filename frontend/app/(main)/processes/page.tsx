"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ProcessSummaryResponse, ProcessGroupsResponse } from "@/lib/api";

// ---------------------------------------------------------------------------
// Review queue helpers
// ---------------------------------------------------------------------------

type ReviewCategory = "needs_review" | "in_progress" | "failed" | "pending";

function reviewCategory(p: ProcessSummaryResponse): ReviewCategory {
  if (p.extraction_status === "completed") return "needs_review";
  if (p.extraction_status === "failed") return "failed";
  if (p.extraction_status === "processing") return "in_progress";
  return "pending";
}

const REVIEW_CATEGORY_LABELS: Record<ReviewCategory, string> = {
  needs_review: "Needs review",
  in_progress: "Processing",
  failed: "Failed",
  pending: "Pending",
};

const REVIEW_CATEGORY_COLORS: Record<ReviewCategory, string> = {
  needs_review: "bg-blue-50 text-blue-700 border-blue-200",
  in_progress: "bg-yellow-50 text-yellow-700 border-yellow-200",
  failed: "bg-red-50 text-red-700 border-red-200",
  pending: "bg-gray-50 text-gray-500 border-gray-200",
};

// ---------------------------------------------------------------------------
// Review queue summary panel
// ---------------------------------------------------------------------------

function ReviewQueueSummary({ processes }: { processes: ProcessSummaryResponse[] }) {
  const byCategory = processes.reduce<Record<ReviewCategory, number>>(
    (acc, p) => { acc[reviewCategory(p)]++; return acc; },
    { needs_review: 0, in_progress: 0, failed: 0, pending: 0 }
  );
  const needsReview = byCategory.needs_review;

  if (processes.length === 0) return null;

  return (
    <div className="border border-blue-200 bg-blue-50 rounded-lg p-4 mb-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-blue-900 mb-0.5">
            Review queue
          </h2>
          <p className="text-xs text-blue-700">
            {needsReview > 0
              ? `${needsReview} process${needsReview !== 1 ? "es" : ""} ready for human review.`
              : "No processes currently awaiting review."}
          </p>
        </div>
        <div className="flex gap-3 shrink-0">
          {(Object.entries(byCategory) as [ReviewCategory, number][])
            .filter(([, count]) => count > 0)
            .map(([cat, count]) => (
              <div key={cat} className="text-center">
                <div className="text-lg font-bold text-blue-900">{count}</div>
                <div className="text-[10px] text-blue-600">{REVIEW_CATEGORY_LABELS[cat]}</div>
              </div>
            ))}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Extraction status badge
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: string }) {
  const colours: Record<string, string> = {
    completed: "bg-green-100 text-green-700",
    pending: "bg-yellow-100 text-yellow-700",
    failed: "bg-red-100 text-red-700",
  };
  const cls = colours[status] ?? "bg-gray-100 text-gray-700";
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Similarity groups panel
// ---------------------------------------------------------------------------

function GroupsPanel({ groups }: { groups: ProcessGroupsResponse["groups"] }) {
  const multi = groups.filter((g) => g.process_ids.length > 1);
  if (multi.length === 0) return null;
  return (
    <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6">
      <h2 className="text-sm font-semibold text-amber-800 mb-1">
        Similarity groups — {multi.length} cluster{multi.length !== 1 ? "s" : ""} detected
      </h2>
      <p className="text-xs text-amber-700 mb-3">
        Processes below may describe the same operational workflow. Review each group to confirm.
      </p>
      <div className="space-y-3">
        {multi.map((g) => {
          const cohortPct = Math.round(g.cohesion * 100);
          const verdict = g.recommend_merge ? "merge candidate" : "related";
          return (
            <div key={g.cluster_id} className="bg-white border border-amber-200 rounded p-3">
              <div className="flex items-center justify-between gap-3 mb-1.5">
                <span className="text-xs font-semibold text-amber-900">
                  {g.process_ids.length} processes — {cohortPct}% cohesion
                </span>
                <span className={`text-[10px] font-medium px-2 py-0.5 rounded border ${
                  g.recommend_merge
                    ? "bg-amber-100 text-amber-800 border-amber-300"
                    : "bg-gray-100 text-gray-600 border-gray-200"
                }`}>
                  {verdict}
                </span>
              </div>
              {g.merge_note && (
                <p className="text-[11px] text-amber-700 italic mb-1.5">{g.merge_note}</p>
              )}
              <div className="flex flex-wrap gap-1">
                {g.process_ids.slice(0, 4).map((pid) => (
                  <Link
                    key={pid}
                    href={`/processes/${pid}`}
                    className="text-[10px] px-1.5 py-0.5 bg-amber-100 text-amber-800 rounded hover:bg-amber-200 font-mono truncate max-w-[140px]"
                  >
                    {pid.slice(0, 8)}…
                  </Link>
                ))}
                {g.process_ids.length > 4 && (
                  <span className="text-[10px] text-amber-600">+{g.process_ids.length - 4} more</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main dashboard
// ---------------------------------------------------------------------------

type CategoryFilter = "all" | ReviewCategory;

export default function ProcessDashboard() {
  const [processes, setProcesses] = useState<ProcessSummaryResponse[]>([]);
  const [groups, setGroups] = useState<ProcessGroupsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>("all");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [procs, grps] = await Promise.all([
          api.listProcesses({ limit: 100 }),
          api.getProcessGroups(),
        ]);
        if (!cancelled) {
          // Sort: needs_review first, then in_progress, then others
          const ORDER: ReviewCategory[] = ["needs_review", "in_progress", "pending", "failed"];
          procs.sort((a, b) => ORDER.indexOf(reviewCategory(a)) - ORDER.indexOf(reviewCategory(b)));
          setProcesses(procs);
          setGroups(grps);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load processes");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  // Filter by text and category
  const filtered = processes.filter((p) => {
    const textMatch = !filter || `${p.filename ?? ""} ${p.schema_version ?? ""}`.toLowerCase().includes(filter.toLowerCase());
    const catMatch = categoryFilter === "all" || reviewCategory(p) === categoryFilter;
    return textMatch && catMatch;
  });

  if (loading) {
    return (
      <div className="p-8 text-gray-500">Loading processes…</div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-lg">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Process Explorer</h1>
        <p className="text-sm text-gray-500 mt-1">
          {processes.length} process candidate{processes.length !== 1 ? "s" : ""} extracted
        </p>
      </div>

      {/* Review queue summary */}
      <ReviewQueueSummary processes={processes} />

      {/* Similarity groups panel */}
      {groups && <GroupsPanel groups={groups.groups} />}

      {/* Category filter tabs + text filter */}
      <div className="mb-4 space-y-3">
        <div className="flex items-center gap-1.5 flex-wrap">
          {(["all", "needs_review", "in_progress", "failed", "pending"] as CategoryFilter[]).map((cat) => {
            const count = cat === "all" ? processes.length : processes.filter((p) => reviewCategory(p) === cat).length;
            if (count === 0 && cat !== "all") return null;
            return (
              <button
                key={cat}
                onClick={() => setCategoryFilter(cat)}
                className={[
                  "text-xs px-3 py-1 rounded-full border font-medium transition-colors",
                  categoryFilter === cat
                    ? "bg-blue-600 text-white border-blue-600"
                    : "bg-white text-gray-600 border-gray-300 hover:border-blue-300",
                ].join(" ")}
              >
                {cat === "all" ? "All" : REVIEW_CATEGORY_LABELS[cat]} ({count})
              </button>
            );
          })}
        </div>
        <input
          type="text"
          placeholder="Filter by filename or schema…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {/* Process list */}
      {filtered.length === 0 ? (
        <div className="text-gray-500 text-sm">No processes match your filter.</div>
      ) : (
        <div className="space-y-3">
          {filtered.map((p) => (
            <div
              key={p.extraction_result_id}
              className="bg-white border border-gray-200 rounded-lg p-4 hover:border-blue-300 transition-colors"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className="font-medium text-gray-900 truncate">
                      {p.filename ?? "Unnamed process"}
                    </span>
                    <StatusBadge status={p.extraction_status} />
                    {(() => {
                      const cat = reviewCategory(p);
                      return (
                        <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-medium border ${REVIEW_CATEGORY_COLORS[cat]}`}>
                          {REVIEW_CATEGORY_LABELS[cat]}
                        </span>
                      );
                    })()}
                  </div>
                  <div className="text-xs text-gray-500 font-mono truncate">
                    {p.extraction_result_id}
                  </div>
                  {p.schema_version && (
                    <div className="text-xs text-gray-400 mt-0.5">{p.schema_version}</div>
                  )}
                </div>
                {/* Navigation links */}
                <div className="flex gap-2 shrink-0 flex-wrap justify-end">
                  <Link
                    href={`/processes/${p.extraction_result_id}`}
                    className="text-xs px-2 py-1 bg-blue-50 text-blue-700 rounded hover:bg-blue-100 transition-colors"
                  >
                    Details
                  </Link>
                  <Link
                    href={`/processes/${p.extraction_result_id}/graph`}
                    className="text-xs px-2 py-1 bg-purple-50 text-purple-700 rounded hover:bg-purple-100 transition-colors"
                  >
                    Graph
                  </Link>
                  <Link
                    href={`/processes/${p.extraction_result_id}/timeline`}
                    className="text-xs px-2 py-1 bg-green-50 text-green-700 rounded hover:bg-green-100 transition-colors"
                  >
                    Timeline
                  </Link>
                  <Link
                    href={`/processes/${p.extraction_result_id}?tab=explanations`}
                    className="text-xs px-2 py-1 bg-slate-50 text-slate-600 rounded hover:bg-slate-100 transition-colors"
                  >
                    Explain
                  </Link>
                  {p.extraction_status === "completed" && (
                    <Link
                      href={`/runs/${p.run_id}/review`}
                      className="text-xs px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors font-medium"
                    >
                      Review
                    </Link>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
