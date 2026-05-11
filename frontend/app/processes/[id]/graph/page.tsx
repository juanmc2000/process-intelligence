"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  Node,
  Edge,
  NodeTypes,
  useNodesState,
  useEdgesState,
} from "reactflow";
import "reactflow/dist/style.css";
import { api, GraphResponse } from "@/lib/api";

// ---------------------------------------------------------------------------
// Node colours by type
// ---------------------------------------------------------------------------

const NODE_COLOURS: Record<string, { bg: string; border: string; text: string }> = {
  workflow_step: { bg: "#dbeafe", border: "#3b82f6", text: "#1e3a5f" },
  role: { bg: "#d1fae5", border: "#10b981", text: "#065f46" },
  system: { bg: "#ede9fe", border: "#8b5cf6", text: "#4c1d95" },
  control: { bg: "#fef3c7", border: "#f59e0b", text: "#78350f" },
  decision: { bg: "#fee2e2", border: "#ef4444", text: "#7f1d1d" },
  exception: { bg: "#fce7f3", border: "#ec4899", text: "#831843" },
  handoff: { bg: "#e0f2fe", border: "#0ea5e9", text: "#0c4a6e" },
};

// ---------------------------------------------------------------------------
// Custom node renderer — a simple card with colour by type
// ---------------------------------------------------------------------------

function ProcessNode({ data }: { data: { label: string; nodeType: string } }) {
  const colours = NODE_COLOURS[data.nodeType] ?? {
    bg: "#f3f4f6",
    border: "#9ca3af",
    text: "#1f2937",
  };
  return (
    <div
      style={{
        background: colours.bg,
        border: `2px solid ${colours.border}`,
        color: colours.text,
        borderRadius: 8,
        padding: "8px 14px",
        minWidth: 120,
        maxWidth: 200,
        fontSize: 12,
        fontWeight: 600,
        textAlign: "center",
        boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
      }}
    >
      <div
        style={{
          fontSize: 9,
          fontWeight: 400,
          opacity: 0.7,
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          marginBottom: 2,
        }}
      >
        {data.nodeType.replace("_", " ")}
      </div>
      {data.label}
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
// Metadata panel
// ---------------------------------------------------------------------------

function MetadataPanel({
  metadata,
  onClose,
}: {
  metadata: Record<string, unknown>;
  onClose: () => void;
}) {
  return (
    <div className="absolute top-4 right-4 z-10 bg-white border border-gray-200 rounded-lg shadow-lg p-4 w-64">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-900">Graph Info</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xs">
          ✕
        </button>
      </div>
      <div className="space-y-1 text-xs text-gray-600">
        <div>
          <span className="font-medium">Nodes:</span>{" "}
          {String(metadata.node_count ?? 0)}
        </div>
        <div>
          <span className="font-medium">Edges:</span>{" "}
          {String(metadata.edge_count ?? 0)}
        </div>
        {Boolean(
          metadata.node_type_counts &&
            typeof metadata.node_type_counts === "object"
        ) && (
            <div className="mt-2">
              <div className="font-medium mb-1">By type:</div>
              {Object.entries(
                metadata.node_type_counts as Record<string, number>
              ).map(([t, n]) => (
                <div key={t} className="flex justify-between">
                  <span>{t.replace(/_/g, " ")}</span>
                  <span>{String(n)}</span>
                </div>
              ))}
            </div>
          )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main graph page
// ---------------------------------------------------------------------------

export default function ProcessGraphPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [graphData, setGraphData] = useState<GraphResponse | null>(null);
  const [showPanel, setShowPanel] = useState(true);

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    async function load() {
      try {
        const data = await api.getProcessGraph(id);
        if (cancelled) return;
        setGraphData(data);
        // Map API graph payload to React Flow nodes/edges
        const rfNodes: Node[] = data.graph.nodes.map((n) => ({
          id: n.id,
          type: n.type,
          position: n.position,
          data: { ...n.data, nodeType: n.type },
        }));
        const rfEdges: Edge[] = data.graph.edges.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          type: "smoothstep",
          label: e.label,
          animated: e.animated ?? false,
          style: { stroke: "#94a3b8" },
        }));
        setNodes(rfNodes);
        setEdges(rfEdges);
      } catch (e) {
        if (!cancelled)
          setError(e instanceof Error ? e.message : "Failed to load graph");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [id, setNodes, setEdges]);

  if (loading) {
    return <div className="p-8 text-gray-500">Loading workflow graph…</div>;
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

  if (!graphData || nodes.length === 0) {
    return (
      <div className="p-8 text-gray-500">
        No graph data available for this process.
      </div>
    );
  }

  return (
    <div className="relative" style={{ height: "calc(100vh - 4rem)" }}>
      {/* Toolbar */}
      <div className="absolute top-4 left-4 z-10 flex gap-2">
        <a
          href={`/processes/${id}`}
          className="text-xs px-3 py-1.5 bg-white border border-gray-200 rounded shadow-sm text-gray-700 hover:bg-gray-50"
        >
          ← Details
        </a>
        <a
          href={`/processes/${id}/timeline`}
          className="text-xs px-3 py-1.5 bg-white border border-gray-200 rounded shadow-sm text-gray-700 hover:bg-gray-50"
        >
          Timeline
        </a>
        {!showPanel && (
          <button
            onClick={() => setShowPanel(true)}
            className="text-xs px-3 py-1.5 bg-white border border-gray-200 rounded shadow-sm text-gray-700 hover:bg-gray-50"
          >
            Info
          </button>
        )}
      </div>

      {/* Metadata panel */}
      {showPanel && graphData.graph.metadata && (
        <MetadataPanel
          metadata={graphData.graph.metadata}
          onClose={() => setShowPanel(false)}
        />
      )}

      {/* React Flow canvas */}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.2}
        maxZoom={2}
        attributionPosition="bottom-right"
      >
        <Background gap={16} color="#e5e7eb" />
        <Controls />
        <MiniMap nodeColor={(n) => NODE_COLOURS[n.type ?? ""]?.border ?? "#9ca3af"} />
      </ReactFlow>
    </div>
  );
}
