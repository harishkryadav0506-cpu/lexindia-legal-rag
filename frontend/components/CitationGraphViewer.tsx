"use client";

import React, { useEffect, useRef, useState } from "react";
import cytoscape, { Core } from "cytoscape";
import { Network, RefreshCw, ZoomIn, ZoomOut, Maximize2 } from "lucide-react";
import { fetchCitationGraph } from "@/lib/api";
import { GraphResponse } from "@/types";

interface CitationGraphViewerProps {
  initialSectionId?: string;
}

export default function CitationGraphViewer({
  initialSectionId = "Section 80C",
}: CitationGraphViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  const [sectionId, setSectionId] = useState(initialSectionId);
  const [hops, setHops] = useState(2);
  const [loading, setLoading] = useState(false);
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [graphData, setGraphData] = useState<GraphResponse | null>(null);

  const loadGraph = async (targetSection: string, targetHops: number) => {
    if (!targetSection) return;
    setLoading(true);
    setSelectedNode(null);
    try {
      const data = await fetchCitationGraph(targetSection, targetHops);
      setGraphData(data);
      renderCytoscape(data);
    } catch (e) {
      console.error("Failed to load citation graph:", e);
    } finally {
      setLoading(false);
    }
  };

  const renderCytoscape = (data: GraphResponse) => {
    if (!containerRef.current) return;

    if (cyRef.current) {
      cyRef.current.destroy();
    }

    const elements: any[] = [];

    // Add nodes
    data.nodes.forEach((n) => {
      let bgColor = "#f59e0b"; // Act (1)
      if (n.authority_level === 2) bgColor = "#3b82f6"; // Rules (2)
      if (n.authority_level === 3) bgColor = "#a855f7"; // Circular (3)
      if (n.authority_level === 4) bgColor = "#14b8a6"; // Instructions (4)

      elements.push({
        data: {
          id: n.id,
          label: n.label,
          authority_level: n.authority_level,
          doc_type: n.doc_type,
          bgColor,
        },
      });
    });

    // Add edges
    data.edges.forEach((e, idx) => {
      elements.push({
        data: {
          id: `e_${idx}`,
          source: e.source,
          target: e.target,
          label: e.relation,
        },
      });
    });

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: "node",
          style: {
            "background-color": "data(bgColor)",
            label: "data(label)",
            color: "#f8fafc",
            "font-size": "10px",
            "font-weight": "bold",
            "text-valign": "center",
            "text-halign": "center",
            width: 38,
            height: 38,
            "border-width": 2,
            "border-color": "#ffffff",
            "text-outline-width": 2,
            "text-outline-color": "#090d16",
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-color": "#fbbf24",
            "border-width": 4,
            width: 44,
            height: 44,
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.5,
            "line-color": "#475569",
            "target-arrow-color": "#94a3b8",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            label: "data(label)",
            "font-size": "8px",
            color: "#94a3b8",
            "text-rotation": "autorotate",
            "text-background-opacity": 0.8,
            "text-background-color": "#0b1120",
            "text-background-padding": "2px",
          },
        },
      ],
      layout: {
        name: "cose",
        animate: false,
        padding: 30,
        componentSpacing: 80,
      },
    });

    cy.on("tap", "node", (evt) => {
      const node = evt.target;
      setSelectedNode(node.data());
    });

    cy.on("tap", (evt) => {
      if (evt.target === cy) {
        setSelectedNode(null);
      }
    });

    cyRef.current = cy;
  };

  useEffect(() => {
    if (initialSectionId) {
      setSectionId(initialSectionId);
      loadGraph(initialSectionId, hops);
    }
    return () => {
      if (cyRef.current) {
        cyRef.current.destroy();
      }
    };
  }, [initialSectionId]);

  return (
    <div className="glass-panel rounded-2xl border border-slate-800 shadow-xl overflow-hidden flex flex-col">
      {/* Graph Toolbar */}
      <div className="p-4 border-b border-slate-800 bg-slate-950/60 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Network className="w-5 h-5 text-amber-400" />
          <h3 className="text-sm font-bold text-slate-100">Statutory Knowledge Graph</h3>
          <span className="text-xs text-slate-500">
            ({graphData?.nodes.length || 0} nodes, {graphData?.edges.length || 0} edges)
          </span>
        </div>

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <input
            type="text"
            value={sectionId}
            onChange={(e) => setSectionId(e.target.value)}
            placeholder="e.g. Section 80C"
            className="bg-slate-900 text-slate-200 border border-slate-700 px-2.5 py-1.5 rounded-lg w-32 sm:w-40 focus:outline-none focus:ring-1 focus:ring-amber-400"
          />
          <select
            value={hops}
            onChange={(e) => setHops(Number(e.target.value))}
            className="bg-slate-900 text-slate-200 border border-slate-700 px-2 py-1.5 rounded-lg focus:outline-none focus:ring-1 focus:ring-amber-400"
          >
            <option value={1}>1 Hop</option>
            <option value={2}>2 Hops</option>
            <option value={3}>3 Hops</option>
          </select>

          <button
            onClick={() => loadGraph(sectionId, hops)}
            disabled={loading}
            className="bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold px-3 py-1.5 rounded-lg flex items-center gap-1 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>Load</span>
          </button>

          {/* Zoom controls */}
          <div className="flex items-center border border-slate-700 rounded-lg overflow-hidden ml-1">
            <button
              onClick={() => cyRef.current?.zoom(cyRef.current.zoom() * 1.2)}
              className="p-1.5 bg-slate-900 hover:bg-slate-800 text-slate-300"
              title="Zoom in"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => cyRef.current?.zoom(cyRef.current.zoom() / 1.2)}
              className="p-1.5 bg-slate-900 hover:bg-slate-800 text-slate-300 border-l border-slate-700"
              title="Zoom out"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => cyRef.current?.fit()}
              className="p-1.5 bg-slate-900 hover:bg-slate-800 text-slate-300 border-l border-slate-700"
              title="Fit to view"
            >
              <Maximize2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Main Canvas & Details Split */}
      <div className="relative flex-1 min-h-[420px] bg-slate-950/80 flex">
        {/* Cytoscape DOM container */}
        <div ref={containerRef} className="w-full h-full min-h-[420px]" />

        {/* Selected Node Inspector Drawer */}
        {selectedNode && (
          <div className="absolute right-3 top-3 bottom-3 w-72 bg-slate-900/95 backdrop-blur-md border border-slate-700 rounded-xl p-4 text-xs shadow-2xl flex flex-col justify-between z-10">
            <div className="space-y-3">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                <span className="font-bold text-amber-400 text-sm">{selectedNode.label}</span>
                <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
                  Level {selectedNode.authority_level}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block mb-1">Document Classification:</span>
                <p className="text-slate-200 capitalize font-medium">{selectedNode.doc_type}</p>
              </div>
              <p className="text-slate-400 text-[11px]">
                Connected in statutory graph via cross-references (READ_WITH, SUBJECT_TO, AMENDED_BY).
              </p>
            </div>

            <button
              onClick={() => {
                setSectionId(selectedNode.label);
                loadGraph(selectedNode.label, hops);
              }}
              className="w-full py-2 bg-slate-800 hover:bg-slate-700 text-amber-400 font-semibold rounded-lg border border-slate-700 transition-colors"
            >
              Re-center Graph Here
            </button>
          </div>
        )}

        {/* Legend Overlay */}
        <div className="absolute left-3 bottom-3 bg-slate-900/90 border border-slate-800 px-3 py-2 rounded-lg text-[10px] space-y-1 z-10">
          <span className="text-slate-400 font-bold block mb-1">Authority Legend:</span>
          <div className="flex items-center gap-1.5 text-slate-300">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500" /> Act / Statute (Level 1)
          </div>
          <div className="flex items-center gap-1.5 text-slate-300">
            <span className="w-2.5 h-2.5 rounded-full bg-blue-500" /> Rules (Level 2)
          </div>
          <div className="flex items-center gap-1.5 text-slate-300">
            <span className="w-2.5 h-2.5 rounded-full bg-purple-500" /> Circulars (Level 3)
          </div>
          <div className="flex items-center gap-1.5 text-slate-300">
            <span className="w-2.5 h-2.5 rounded-full bg-teal-500" /> Instructions (Level 4)
          </div>
        </div>
      </div>
    </div>
  );
}
