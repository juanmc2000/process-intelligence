"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  Node,
  Edge,
  NodeTypes,
  useNodesState,
  useEdgesState,
  BackgroundVariant,
} from "reactflow";
import "reactflow/dist/style.css";
import { api, GraphResponse, ProcessDetailResponse } from "@/lib/api";

// ---------------------------------------------------------------------------
// Node colour palette (tuned for dark canvas)
// ---------------------------------------------------------------------------

const NODE_PALETTE: Record<string, { bg: string; border: string; text: string; dot: string }> = {
  workflow_step: { bg: "#1e3a2e", border: "#10b981", text: "#a7f3d0", dot: "#10b981" },
  role:          { bg: "#1e2a3e", border: "#60a5fa", text: "#bfdbfe", dot: "#60a5fa" },
  system:        { bg: "#2d1e3e", border: "#a78bfa", text: "#ddd6fe", dot: "#a78bfa" },
  control:       { bg: "#3a2d1e", border: "#f59e0b", text: "#fde68a", dot: "#f59e0b" },
  decision:      { bg: "#3a1e1e", border: "#f87171", text: "#fecaca", dot: "#f87171" },
  exception:     { bg: "#3a1e2e", border: "#f472b6", text: "#fbcfe8", dot: "#f472b6" },
  handoff:       { bg: "#1e2e3a", border: "#38bdf8", text: "#bae6fd", dot: "#38bdf8" },
};

const DEFAULT_PALETTE = { bg: "#1e2433", border: "#4b5563", text: "#e5e7eb", dot: "#6b7280" };

// ---------------------------------------------------------------------------
// Custom node
// ---------------------------------------------------------------------------

function ProcessNode({ data }: { data: { label: string; nodeType: string } }) {
  const p = NODE_PALETTE[data.nodeType] ?? DEFAULT_PALETTE;
  return (
    <div
      style={{
        background: p.bg,
        border: `1.5px solid ${p.border}`,
        borderRadius: 10,
        padding: "8px 12px",
        minWidth: 130,
        maxWidth: 200,
        boxShadow: `0 0 0 1px ${p.border}22, 0 4px 12px rgba(0,0,0,0.4)`,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <div style={{ width: 7, height: 7, borderRadius: "50%", background: p.dot, flexShrink: 0 }} />
        <span style={{ fontSize: 12, fontWeight: 600, color: p.text, lineHeight: 1.3 }}>
          {data.label}
        </span>
      </div>
      <div style={{ fontSize: 9, color: p.dot, opacity: 0.7, textTransform: "uppercase", letterSpacing: "0.06em", marginTop: 3, paddingLeft: 13 }}>
        {data.nodeType.replace(/_/g, " ")}
      </div>
    </div>
  );
}

const nodeTypes: NodeTypes = {
  workflow_step: ProcessNode,
  role: ProcessNode,
  system: ProcessNode,
  control: ProcessNode,
  decision: ProcessNode,
  exception: ProcessNode,
  handoff: ProcessNode,
};

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

function IconChevronDown() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5">
      <polyline points="6 9 12 15 18 9" />
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

function IconSparkle() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5">
      <path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6z" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Layer toggle
// ---------------------------------------------------------------------------

type LayerKey = "departments" | "systems" | "approvals" | "exceptions" | "controls" | "roles";

const LAYER_LABELS: Record<LayerKey, string> = {
  departments: "Departments",
  systems: "Systems",
  approvals: "Approvals",
  exceptions: "Exceptions",
  controls: "Controls",
  roles: "Roles",
};

// Maps each ReactFlow node type to the layer that controls its visibility.
// Node types not listed here are always visible.
const NODE_TYPE_LAYER: Partial<Record<string, LayerKey>> = {
  workflow_step: "departments",
  handoff: "departments",
  system: "systems",
  decision: "approvals",
  exception: "exceptions",
  control: "controls",
  role: "roles",
};

// ---------------------------------------------------------------------------
// Confidence ring (compact)
// ---------------------------------------------------------------------------

function ConfidenceRingSmall({ score }: { score: number }) {
  const r = 22;
  const circ = 2 * Math.PI * r;
  const offset = circ - (score / 100) * circ;
  const color = score >= 75 ? "#10b981" : score >= 50 ? "#f59e0b" : "#ef4444";
  return (
    <div className="relative w-14 h-14">
      <svg className="w-14 h-14 -rotate-90" viewBox="0 0 56 56">
        <circle cx="28" cy="28" r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="5" />
        <circle cx="28" cy="28" r={r} fill="none" stroke={color} strokeWidth="5"
          strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round" />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-[13px] font-bold" style={{ color }}>{score}%</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Confidence helpers
// ---------------------------------------------------------------------------

const CONFIDENCE_DIMENSION_LABELS: Record<string, string> = {
  workflow_step_count: "Workflow steps",
  decision_point_count: "Decision points",
  system_touchpoint_count: "System touchpoints",
  role_count: "Roles",
  control_count: "Controls",
  exception_count: "Exceptions",
  change_event_count: "Change events",
};

function deriveConfidenceScore(summary: Record<string, number> | null): number {
  if (!summary) return 0;
  const populated = Object.values(summary).filter((v) => v > 0).length;
  const total = Object.keys(summary).length || 1;
  return Math.round(50 + (populated / total) * 40);
}

function deriveConfidenceLabel(score: number): string {
  if (score >= 75) return "High";
  if (score >= 58) return "Medium";
  return "Low";
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function SpatialWorkflowPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [graphData, setGraphData] = useState<GraphResponse | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  const [layers, setLayers] = useState<Record<LayerKey, boolean>>({
    departments: true,
    systems: true,
    approvals: true,
    exceptions: true,
    controls: true,
    roles: true,
  });

  const [confidenceSummary, setConfidenceSummary] = useState<Record<string, number> | null>(null);

  // Canonical full node/edge sets — source of truth for filtering.
  const allNodesRef = useRef<Node[]>([]);
  const allEdgesRef = useRef<Edge[]>([]);

  // Compute which node IDs are visible given current layer toggles.
  function getVisibleNodeIds(allNodes: Node[], activeLayers: Record<LayerKey, boolean>): Set<string> {
    const ids = new Set<string>();
    for (const n of allNodes) {
      const layer = NODE_TYPE_LAYER[n.type ?? ""];
      if (!layer || activeLayers[layer]) {
        ids.add(n.id);
      }
    }
    return ids;
  }

  useEffect(() => {
    if (!id) return;
    let cancelled = false;

    Promise.all([
      api.getProcessGraph(id),
      api.getProcess(id).catch(() => null as ProcessDetailResponse | null),
    ]).then(([graphResult, processResult]) => {
      if (cancelled) return;
      setGraphData(graphResult);
      if (processResult?.confidence_summary) {
        setConfidenceSummary(processResult.confidence_summary as Record<string, number>);
      }
      const rfNodes: Node[] = graphResult.graph.nodes.map((n) => ({
        id: n.id,
        type: n.type,
        position: n.position,
        data: { ...n.data, nodeType: n.type },
      }));
      const rfEdges: Edge[] = graphResult.graph.edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        type: "smoothstep",
        label: e.label,
        animated: e.animated ?? false,
        style: { stroke: "#475569", strokeWidth: 1.5 },
        labelStyle: { fontSize: 10, fill: "#94a3b8", fontWeight: 500 },
        labelBgStyle: { fill: "#0f1d33", fillOpacity: 0.8 },
      }));
      allNodesRef.current = rfNodes;
      allEdgesRef.current = rfEdges;
      setNodes(rfNodes);
      setEdges(rfEdges);
      setLoading(false);
    }).catch((e) => {
      if (!cancelled) { setError(e instanceof Error ? e.message : "Failed to load graph"); setLoading(false); }
    });
    return () => { cancelled = true; };
  }, [id, setNodes, setEdges]);

  const confidenceScore = deriveConfidenceScore(confidenceSummary);
  const confidenceLabel = deriveConfidenceLabel(confidenceScore);

  // Re-filter whenever layer toggles change, preserving zoom/pan state.
  useEffect(() => {
    if (allNodesRef.current.length === 0) return;
    const visibleIds = getVisibleNodeIds(allNodesRef.current, layers);
    setNodes(allNodesRef.current.filter((n) => visibleIds.has(n.id)));
    setEdges(allEdgesRef.current.filter(
      (e) => visibleIds.has(e.source) && visibleIds.has(e.target)
    ));
  }, [layers, setNodes, setEdges]);

  const workflowName = graphData?.graph.metadata?.process_name
    ? String(graphData.graph.metadata.process_name)
    : "Workflow";

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-[var(--text-muted)] text-sm" style={{ background: "var(--navy-900)" }}>
        Loading workflow graph…
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8" style={{ background: "var(--navy-900)" }}>
        <div className="p-4 text-sm rounded-lg border" style={{ color: "var(--danger)", borderColor: "rgba(239,68,68,0.3)", background: "rgba(239,68,68,0.08)" }}>
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full" style={{ background: "var(--navy-950)" }}>
      {/* Dark header */}
      <div className="shrink-0 px-6 py-0" style={{ background: "var(--navy-900)", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
        {/* Title row */}
        <div className="flex items-center justify-between gap-4 py-3">
          <div className="flex items-center gap-3 min-w-0">
            <Link
              href={`/processes/${id}`}
              className="text-white/40 hover:text-white/70 transition-colors text-[12px]"
            >
              ← Back
            </Link>
            <span className="text-white/20">|</span>
            <h1 className="text-[16px] font-semibold text-white truncate">{workflowName}</h1>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-white/10 text-white/50 border border-white/10 shrink-0">
              Draft
            </span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button disabled title="Coming soon" className="flex items-center gap-1.5 px-3 py-1.5 rounded-btn text-[12px] font-medium text-white/25 border border-white/8 cursor-not-allowed">
              <IconShare />
              Share
            </button>
            <button disabled title="Coming soon" className="flex items-center gap-1.5 px-3 py-1.5 rounded-btn text-[12px] font-medium text-white/25 border border-white/8 cursor-not-allowed">
              Export
              <IconChevronDown />
            </button>
            <button disabled title="Coming soon" className="flex items-center gap-1.5 px-4 py-1.5 rounded-btn text-[12px] font-semibold text-white/30 cursor-not-allowed" style={{ background: "rgba(99,102,241,0.3)" }}>
              Review &amp; Publish
            </button>
          </div>
        </div>

        {/* Tab strip */}
        <div className="flex items-end gap-1">
          {["Overview", "Canvas", "Details", "Insights", "Sources"].map((t) => {
            const isActive = t === "Canvas";
            const isComingSoon = !isActive;
            return (
              <button
                key={t}
                disabled={isComingSoon}
                title={isComingSoon ? "Coming soon" : undefined}
                className={[
                  "px-4 py-2 text-[13px] font-medium border-b-2 transition-colors",
                  isActive
                    ? "border-white text-white"
                    : "border-transparent text-white/25 cursor-not-allowed",
                ].join(" ")}
              >
                {t}
              </button>
            );
          })}
        </div>
      </div>

      {/* Canvas area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left panel */}
        <div
          className="w-48 shrink-0 flex flex-col gap-3 p-3 border-r overflow-y-auto"
          style={{ background: "var(--navy-900)", borderColor: "rgba(255,255,255,0.06)" }}
        >
          {/* Mini-map placeholder label */}
          <div className="rounded-lg overflow-hidden border border-white/8" style={{ background: "var(--navy-800)" }}>
            <div className="px-3 py-2 flex items-center justify-between border-b border-white/5">
              <span className="text-[11px] font-medium text-white/50">Mini map</span>
              <button className="text-white/30 hover:text-white/60 text-[10px]">✕</button>
            </div>
            <div className="h-24 flex items-center justify-center">
              <span className="text-[10px] text-white/20">Canvas preview</span>
            </div>
          </div>

          {/* Zoom indicator */}
          <div className="flex items-center justify-between px-1">
            <button className="text-white/30 hover:text-white/60 text-[11px]">−</button>
            <span className="text-[11px] text-white/40">100%</span>
            <button className="text-white/30 hover:text-white/60 text-[11px]">+</button>
          </div>

          {/* Layers */}
          <div>
            <div className="text-[10px] font-semibold text-white/30 uppercase tracking-wide px-1 mb-2">
              Layers
            </div>
            <div className="space-y-1.5">
              {(Object.keys(LAYER_LABELS) as LayerKey[]).map((k) => (
                <label key={k} className="flex items-center gap-2 px-1 cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={layers[k]}
                    onChange={() => setLayers((prev) => ({ ...prev, [k]: !prev[k] }))}
                    className="w-3.5 h-3.5 accent-accent rounded"
                  />
                  <span className="text-[12px] text-white/50 group-hover:text-white/70 transition-colors">
                    {LAYER_LABELS[k]}
                  </span>
                </label>
              ))}
            </div>
          </div>
        </div>

        {/* React Flow canvas */}
        <div className="flex-1 relative" style={{ background: "#0a1628" }}>
          {nodes.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-white/30">
              <p className="text-[14px]">No graph data available for this process.</p>
              <Link href={`/processes/${id}`} className="text-[12px] text-white/50 hover:text-white/70 underline">
                Back to narrative
              </Link>
            </div>
          ) : (
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              nodeTypes={nodeTypes}
              fitView
              fitViewOptions={{ padding: 0.25 }}
              minZoom={0.1}
              maxZoom={2.5}
              attributionPosition="bottom-right"
            >
              <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="rgba(255,255,255,0.04)" />
              <Controls
                style={{
                  background: "var(--navy-800)",
                  border: "1px solid rgba(255,255,255,0.08)",
                  borderRadius: 8,
                }}
              />
              <MiniMap
                nodeColor={(n) => NODE_PALETTE[n.type ?? ""]?.dot ?? "#4b5563"}
                style={{ background: "var(--navy-850)", border: "1px solid rgba(255,255,255,0.08)" }}
              />
            </ReactFlow>
          )}

          {/* Legend */}
          <div
            className="absolute bottom-4 left-4 flex items-center gap-4 px-3 py-2 rounded-lg text-[10px]"
            style={{ background: "rgba(7,17,31,0.85)", border: "1px solid rgba(255,255,255,0.06)" }}
          >
            <span className="flex items-center gap-1.5 text-white/40">
              <span className="inline-block w-6 border-t border-white/30" />
              Standard flow
            </span>
            <span className="flex items-center gap-1.5 text-white/40">
              <span className="inline-block w-6 border-t border-dashed border-white/30" />
              Exception flow
            </span>
          </div>
        </div>

        {/* Right panel */}
        <div
          className="w-60 shrink-0 flex flex-col gap-0 border-l overflow-y-auto"
          style={{ background: "var(--navy-900)", borderColor: "rgba(255,255,255,0.06)" }}
        >
          {/* AI Suggestions */}
          <div className="p-4 border-b border-white/5">
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-[13px] font-semibold text-white">AI Suggestions</h3>
              <span className="text-[10px] text-white/30 italic">Coming soon</span>
            </div>
            <p className="text-[11px] text-white/30 italic mt-2">
              AI-powered suggestions will appear here once the analysis pipeline is connected.
            </p>
            <button
              disabled
              title="Coming soon"
              className="mt-4 w-full py-2 rounded-btn text-[12px] font-medium text-white/25 border border-white/8 cursor-not-allowed"
            >
              Ask AI about this workflow
            </button>
          </div>

          {/* Confidence */}
          <div className="p-4">
            <h3 className="text-[13px] font-semibold text-white mb-3">Confidence</h3>
            {confidenceSummary ? (
              <>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-[12px] text-white/50 mb-1">Overall — {confidenceLabel}</div>
                    <div className="text-[11px] text-white/30">
                      {Object.values(confidenceSummary).filter((v) => v > 0).length} of{" "}
                      {Object.keys(confidenceSummary).length} dimensions populated
                    </div>
                  </div>
                  <ConfidenceRingSmall score={confidenceScore} />
                </div>
                <div className="mt-3 pt-3 border-t border-white/5 space-y-1.5">
                  {Object.entries(confidenceSummary).map(([key, val]) => (
                    <div key={key} className="flex items-center justify-between text-[11px]">
                      <span className="text-white/35 truncate">
                        {CONFIDENCE_DIMENSION_LABELS[key] ?? key}
                      </span>
                      <span className={val > 0 ? "text-emerald-400" : "text-white/20"}>
                        {val > 0 ? val : "—"}
                      </span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <p className="text-[11px] text-white/30 italic">
                Confidence data not available for this process.
              </p>
            )}

            {/* Graph stats */}
            {graphData?.graph.metadata && (
              <div className="mt-4 pt-4 border-t border-white/5 space-y-2">
                <div className="flex justify-between text-[11px]">
                  <span className="text-white/35">Nodes</span>
                  <span className="text-white/60">{String(graphData.graph.metadata.node_count ?? nodes.length)}</span>
                </div>
                <div className="flex justify-between text-[11px]">
                  <span className="text-white/35">Edges</span>
                  <span className="text-white/60">{String(graphData.graph.metadata.edge_count ?? edges.length)}</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
