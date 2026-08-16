import {
  Background,
  Controls,
  Edge,
  MiniMap,
  Node,
  ReactFlow,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useEffect } from "react";
import type { GraphData } from "../types";

const KIND_COLORS = {
  claim: "#b7772b",
  concept: "#2e7057",
  hypothesis: "#71588a",
};

function createPosition(index: number, total: number) {
  const angle = (index / Math.max(total, 1)) * Math.PI * 2;
  const ring = 180 + Math.floor(index / 12) * 120;
  return { x: 420 + Math.cos(angle) * ring, y: 300 + Math.sin(angle) * ring };
}

function mapNodes(graph: GraphData): Node[] {
  return graph.nodes.map((record, index) => ({
    id: record.id,
    position: createPosition(index, graph.nodes.length),
    data: { label: record.label },
    ariaLabel: `${record.kind}: ${record.label}. Status: ${record.status}`,
    style: {
      width: record.kind === "concept" ? 150 : 190,
      border: `1px solid ${KIND_COLORS[record.kind]}`,
      borderRadius: record.kind === "concept" ? 999 : 12,
      background: "#fffdf8",
      color: "#202622",
      fontSize: 12,
      lineHeight: 1.35,
      padding: "10px 12px",
      boxShadow: "0 6px 20px rgba(28, 40, 33, 0.08)",
    },
  }));
}

function mapEdges(graph: GraphData): Edge[] {
  return graph.edges.map((record) => ({
    id: record.id,
    source: record.source,
    target: record.target,
    label: record.relationship,
    style: { stroke: record.status === "contested" ? "#a75246" : "#9aa69e" },
    labelStyle: { fontSize: 10, fill: "#637069" },
  }));
}

export function KnowledgeGraph({ graph }: { graph: GraphData }) {
  const [nodes, setNodes, onNodesChange] = useNodesState(mapNodes(graph));
  const [edges, setEdges, onEdgesChange] = useEdgesState(mapEdges(graph));

  useEffect(() => {
    setNodes(mapNodes(graph));
    setEdges(mapEdges(graph));
  }, [graph, setEdges, setNodes]);

  if (graph.nodes.length === 0) {
    return (
      <div className="empty-graph">
        <div className="empty-orbit"><span /><span /><span /></div>
        <h2>No confirmed knowledge yet</h2>
        <p>Run browser research, inspect its draft, and confirm the cited evidence. Trusted nodes will appear here.</p>
      </div>
    );
  }

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      fitView
      minZoom={0.2}
      maxZoom={1.8}
      nodesFocusable
      edgesFocusable
      autoPanOnNodeFocus
      aria-label="Confirmed knowledge graph"
    >
      <Background color="#d7d8d0" gap={28} size={1} />
      <Controls showInteractive={false} />
      <MiniMap nodeColor={(node) => String(node.style?.borderColor ?? "#2e7057")} pannable zoomable />
    </ReactFlow>
  );
}
