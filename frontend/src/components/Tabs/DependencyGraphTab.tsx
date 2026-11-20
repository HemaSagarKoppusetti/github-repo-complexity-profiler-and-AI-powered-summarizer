import React, { useEffect, useRef, useState } from 'react';
import cytoscape from 'cytoscape';
import dagre from 'cytoscape-dagre';
import { GraphData } from '../../types/analysis';
import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  Search,
  AlertTriangle,
  Package,
  Layers,
} from 'lucide-react';

// Register dagre layout
cytoscape.use(dagre);

interface DependencyGraphTabProps {
  data: GraphData;
}

export const DependencyGraphTab: React.FC<DependencyGraphTabProps> = ({ data }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);

  const [searchTerm, setSearchTerm] = useState<string>('');
  const [selectedNode, setSelectedNode] = useState<{
    id: string;
    inDegree: number;
    outDegree: number;
    inCycle: boolean;
  } | null>(null);

  const { stats, hub_modules, cycles, external_packages, graph_elements } = data;

  useEffect(() => {
    if (!containerRef.current) return;

    const elements: cytoscape.ElementDefinition[] = [];

    if (graph_elements && graph_elements.nodes) {
      graph_elements.nodes.forEach((n) => {
        elements.push({
          data: {
            id: n.id,
            label: n.label,
            inDegree: n.in_degree,
            outDegree: n.out_degree,
            inCycle: n.in_cycle,
          },
        });
      });
      graph_elements.edges.forEach((e) => {
        elements.push({
          data: {
            source: e.source,
            target: e.target,
          },
        });
      });
    } else {
      // Fallback from raw nodes/edges
      const cycleNodes = new Set(cycles.flat());
      const inDegMap: Record<string, number> = {};
      data.edges.forEach(([, dst]) => {
        inDegMap[dst] = (inDegMap[dst] || 0) + 1;
      });

      data.nodes.forEach((node) => {
        elements.push({
          data: {
            id: node,
            label: node.split('.').pop() || node,
            inDegree: inDegMap[node] || 0,
            outDegree: 0,
            inCycle: cycleNodes.has(node),
          },
        });
      });

      data.edges.forEach(([src, dst]) => {
        elements.push({
          data: { source: src, target: dst },
        });
      });
    }

    const cy = cytoscape({
      container: containerRef.current,
      elements: elements,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': (ele: any) =>
              ele.data('inCycle') ? '#ef4444' : '#3b82f6',
            label: 'data(label)',
            color: '#cbd5e1',
            'font-size': '11px',
            'font-family': 'monospace',
            'text-valign': 'bottom',
            'text-margin-y': 5,
            width: (ele: any) => 20 + Math.min(ele.data('inDegree') * 8, 40),
            height: (ele: any) => 20 + Math.min(ele.data('inDegree') * 8, 40),
            'border-width': 2,
            'border-color': '#1e293b',
          },
        },
        {
          selector: 'node:selected',
          style: {
            'border-width': 3,
            'border-color': '#f59e0b',
            'background-color': '#f59e0b',
          },
        },
        {
          selector: 'edge',
          style: {
            width: 1.5,
            'line-color': '#475569',
            'target-arrow-color': '#64748b',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            opacity: 0.6,
          },
        },
        {
          selector: '.highlighted',
          style: {
            'background-color': '#10b981',
            'line-color': '#10b981',
            'target-arrow-color': '#10b981',
            opacity: 1,
            'z-index': 99,
          },
        },
        {
          selector: '.dimmed',
          style: {
            opacity: 0.15,
          },
        },
      ],
      layout: {
        name: elements.length > 50 ? 'cose' : 'dagre',
        animate: false,
      } as any,
    });

    cy.on('tap', 'node', (evt) => {
      const node = evt.target;
      setSelectedNode({
        id: node.data('id'),
        inDegree: node.data('inDegree'),
        outDegree: node.data('outDegree'),
        inCycle: node.data('inCycle'),
      });

      // Highlight neighborhood
      cy.elements().removeClass('highlighted dimmed');
      const neighborhood = node.neighborhood().add(node);
      cy.elements().difference(neighborhood).addClass('dimmed');
      neighborhood.addClass('highlighted');
    });

    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        setSelectedNode(null);
        cy.elements().removeClass('highlighted dimmed');
      }
    });

    cyRef.current = cy;

    return () => {
      cy.destroy();
    };
  }, [data]);

  const handleSearch = () => {
    if (!cyRef.current || !searchTerm.trim()) return;
    const cy = cyRef.current;
    const found = cy.nodes().filter((n) =>
      n.data('id').toLowerCase().includes(searchTerm.toLowerCase())
    );

    if (found.length > 0) {
      cy.elements().removeClass('highlighted dimmed');
      found.addClass('highlighted');
      cy.animate({
        center: { eles: found },
        zoom: 1.5,
        duration: 400,
      });
      setSelectedNode({
        id: found.first().data('id'),
        inDegree: found.first().data('inDegree'),
        outDegree: found.first().data('outDegree'),
        inCycle: found.first().data('inCycle'),
      });
    }
  };

  const handleZoomIn = () => cyRef.current?.zoom(cyRef.current.zoom() * 1.25);
  const handleZoomOut = () => cyRef.current?.zoom(cyRef.current.zoom() * 0.8);
  const handleFit = () => {
    cyRef.current?.fit();
    cyRef.current?.elements().removeClass('highlighted dimmed');
    setSelectedNode(null);
  };

  return (
    <div className="space-y-6">
      {/* Top Stats Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
          <p className="text-xs text-slate-500 font-medium">Nodes (Modules)</p>
          <p className="text-xl font-bold mt-1 text-slate-900 dark:text-white">
            {stats.node_count}
          </p>
        </div>
        <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
          <p className="text-xs text-slate-500 font-medium">Edges (Imports)</p>
          <p className="text-xl font-bold mt-1 text-slate-900 dark:text-white">
            {stats.edge_count}
          </p>
        </div>
        <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
          <p className="text-xs text-slate-500 font-medium">Graph Density</p>
          <p className="text-xl font-bold mt-1 text-slate-900 dark:text-white">
            {stats.density}
          </p>
        </div>
        <div
          className={`p-4 rounded-xl border ${
            stats.cycle_count > 0
              ? 'border-rose-200 dark:border-rose-900 bg-rose-50/50 dark:bg-rose-950/20'
              : 'border-emerald-200 dark:border-emerald-900 bg-emerald-50/50 dark:bg-emerald-950/20'
          }`}
        >
          <p
            className={`text-xs font-medium ${
              stats.cycle_count > 0 ? 'text-rose-700 dark:text-rose-400' : 'text-emerald-700 dark:text-emerald-400'
            }`}
          >
            Circular Dependencies
          </p>
          <p
            className={`text-xl font-bold mt-1 ${
              stats.cycle_count > 0 ? 'text-rose-700 dark:text-rose-400' : 'text-emerald-700 dark:text-emerald-400'
            }`}
          >
            {stats.cycle_count === 0 ? 'None (Clean)' : `${stats.cycle_count} Detected`}
          </p>
        </div>
      </div>

      {/* Circular Dependencies Alert if present */}
      {cycles.length > 0 && (
        <div className="p-4 rounded-xl border border-rose-300 dark:border-rose-900 bg-rose-50 dark:bg-rose-950/40 space-y-2">
          <h4 className="text-xs font-bold text-rose-800 dark:text-rose-300 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-600" />
            Detected {cycles.length} Circular Dependency Loop{cycles.length > 1 ? 's' : ''}:
          </h4>
          <div className="space-y-1">
            {cycles.map((cycle, idx) => (
              <div key={idx} className="p-2 bg-white dark:bg-slate-900 rounded font-mono text-xs text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-800">
                {cycle.join(' → ')} → {cycle[0]}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Interactive Cytoscape Canvas & Controls */}
      <div className="relative border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden bg-slate-900 shadow-sm">
        {/* Floating Toolbar */}
        <div className="absolute top-4 left-4 z-10 flex items-center gap-2">
          <div className="relative">
            <input
              type="text"
              placeholder="Find module..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              className="pl-8 pr-3 py-1.5 text-xs rounded-lg bg-slate-800/90 text-white placeholder-slate-400 border border-slate-700 backdrop-blur focus:outline-none focus:ring-1 focus:ring-blue-500 w-44 sm:w-56"
            />
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
          </div>
          <button
            onClick={handleSearch}
            className="px-2.5 py-1.5 text-xs font-medium rounded-lg bg-blue-600 hover:bg-blue-700 text-white transition-colors"
          >
            Locate
          </button>
        </div>

        <div className="absolute top-4 right-4 z-10 flex items-center gap-1.5 bg-slate-800/90 backdrop-blur border border-slate-700 rounded-lg p-1 text-slate-300">
          <button onClick={handleZoomIn} className="p-1.5 hover:text-white rounded hover:bg-slate-700" title="Zoom in">
            <ZoomIn className="w-4 h-4" />
          </button>
          <button onClick={handleZoomOut} className="p-1.5 hover:text-white rounded hover:bg-slate-700" title="Zoom out">
            <ZoomOut className="w-4 h-4" />
          </button>
          <button onClick={handleFit} className="p-1.5 hover:text-white rounded hover:bg-slate-700" title="Reset view">
            <Maximize2 className="w-4 h-4" />
          </button>
        </div>

        {/* Legend */}
        <div className="absolute bottom-4 left-4 z-10 bg-slate-800/90 backdrop-blur border border-slate-700 rounded-lg px-3 py-2 text-[11px] text-slate-300 flex items-center gap-4">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-blue-500"></span> Standard Module
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500"></span> Circular Cycle
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span> Connected Neighbor
          </span>
        </div>

        {/* Selected Node Details Drawer */}
        {selectedNode && (
          <div className="absolute bottom-4 right-4 z-10 bg-slate-800/95 backdrop-blur border border-slate-700 rounded-xl p-3 text-xs text-white max-w-xs shadow-lg">
            <p className="font-mono font-bold text-blue-400 break-all">{selectedNode.id}</p>
            <div className="mt-2 grid grid-cols-2 gap-2 text-slate-300 text-[11px]">
              <div>In-Degree: <span className="font-bold text-white">{selectedNode.inDegree}</span></div>
              <div>Out-Degree: <span className="font-bold text-white">{selectedNode.outDegree}</span></div>
            </div>
            {selectedNode.inCycle && (
              <p className="mt-2 text-rose-400 font-bold text-[10px]">⚠️ Belongs to circular dependency</p>
            )}
          </div>
        )}

        <div ref={containerRef} className="w-full h-[550px]" />
      </div>

      {/* Hub Modules and External Dependencies */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Hub Modules */}
        <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
          <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
            <Layers className="w-4 h-4 text-blue-500" />
            Top Hub Modules (Highest In-Degree)
          </h3>
          <div className="space-y-2">
            {hub_modules.length === 0 ? (
              <p className="text-xs text-slate-400 py-2">No central hub modules detected.</p>
            ) : (
              hub_modules.map((h, idx) => (
                <div
                  key={idx}
                  className="p-2.5 rounded-xl border border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50 flex items-center justify-between text-xs"
                >
                  <span className="font-mono text-slate-800 dark:text-slate-200 truncate">
                    {h.module}
                  </span>
                  <span className="px-2 py-0.5 rounded-full bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400 font-bold">
                    Imported by {h.imported_by}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* External Packages */}
        <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
          <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
            <Package className="w-4 h-4 text-indigo-500" />
            External Packages Referenced ({external_packages.length})
          </h3>
          <div className="flex flex-wrap gap-1.5 max-h-48 overflow-y-auto">
            {external_packages.length === 0 ? (
              <p className="text-xs text-slate-400 py-2">No external package dependencies.</p>
            ) : (
              external_packages.map((pkg, idx) => (
                <span
                  key={idx}
                  className="px-2.5 py-1 rounded-lg text-xs font-mono bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700"
                >
                  {pkg}
                </span>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
