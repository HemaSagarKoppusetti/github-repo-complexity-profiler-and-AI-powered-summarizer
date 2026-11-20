import React from 'react';
import { ComplexityData } from '../../types/analysis';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { AlertTriangle, Award, CheckCircle } from 'lucide-react';

interface ComplexityTabProps {
  data: ComplexityData;
}

export const ComplexityTab: React.FC<ComplexityTabProps> = ({ data }) => {
  const { summary, results } = data;
  const { rank_distribution, top_complex_functions } = summary;

  const rankColors: Record<string, string> = {
    A: '#10b981', // green (1-5)
    B: '#3b82f6', // blue (6-10)
    C: '#f59e0b', // amber (11-15)
    D: '#f97316', // orange (16-20)
    E: '#ef4444', // red (21-25)
    F: '#b91c1c', // dark red (26+)
  };

  const chartData = Object.entries(rank_distribution).map(([rank, count]) => ({
    rank: `Rank ${rank}`,
    count,
    color: rankColors[rank] || '#64748b',
  }));

  return (
    <div className="space-y-6">
      {/* Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
          <p className="text-xs text-slate-500 uppercase font-medium">Total Functions</p>
          <p className="text-2xl font-bold mt-1 text-slate-900 dark:text-white">
            {summary.total_functions}
          </p>
          <span className="text-xs text-slate-400 mt-1 block">
            Across {summary.total_files_analysed} Python files
          </span>
        </div>
        <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
          <p className="text-xs text-slate-500 uppercase font-medium">Avg Maintainability Index</p>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl font-bold text-slate-900 dark:text-white">
              {summary.avg_mi_score}
            </span>
            <span className="text-xs text-slate-400">/ 100</span>
          </div>
          <span className="text-xs text-emerald-600 dark:text-emerald-400 mt-1 flex items-center gap-1 font-medium">
            <CheckCircle className="w-3.5 h-3.5" />
            {summary.avg_mi_score >= 65 ? 'Good maintainability' : summary.avg_mi_score >= 35 ? 'Moderate' : 'Difficult'}
          </span>
        </div>
        <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
          <p className="text-xs text-slate-500 uppercase font-medium">Low MI Files (MI &lt; 20)</p>
          <p className="text-2xl font-bold mt-1 text-rose-600 dark:text-rose-400">
            {summary.low_mi_file_count}
          </p>
          <span className="text-xs text-slate-400 mt-1 block">
            Require urgent structural refactoring
          </span>
        </div>
      </div>

      {/* Charts & Functions Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* CC Rank Distribution Chart */}
        <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
          <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
            <Award className="w-4 h-4 text-blue-500" />
            Cyclomatic Complexity (CC) Rank Distribution
          </h3>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <XAxis dataKey="rank" tick={{ fontSize: 12 }} stroke="#94a3b8" />
                <YAxis tick={{ fontSize: 12 }} stroke="#94a3b8" allowDecimals={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#1e293b',
                    borderColor: '#334155',
                    color: '#fff',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                />
                <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                  {chartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="flex items-center justify-between text-[11px] text-slate-500 mt-3 pt-3 border-t border-slate-100 dark:border-slate-800">
            <span>A: Simple (1-5)</span>
            <span>B: Slight (6-10)</span>
            <span>C: Complex (11-15)</span>
            <span>D-F: High Risk (16+)</span>
          </div>
        </div>

        {/* Top Complex Functions List */}
        <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
          <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-500" />
            Top Most Complex Functions
          </h3>
          <div className="space-y-3">
            {top_complex_functions.length === 0 ? (
              <p className="text-xs text-slate-400 py-4 text-center">No functions found.</p>
            ) : (
              top_complex_functions.map((fn, idx) => {
                const fname = fn.filepath ? fn.filepath.split(/[/\\]/).pop() : '';
                return (
                  <div
                    key={idx}
                    className="p-3 rounded-xl border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40 flex items-center justify-between gap-3"
                  >
                    <div className="min-w-0">
                      <p className="font-mono text-xs font-bold text-slate-900 dark:text-white truncate">
                        {fn.name}()
                      </p>
                      <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate mt-0.5">
                        {fname} • line {fn.lineno}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="px-2 py-0.5 rounded text-xs font-bold bg-rose-50 text-rose-700 dark:bg-rose-950 dark:text-rose-400 border border-rose-200 dark:border-rose-800">
                        CC {fn.complexity}
                      </span>
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300">
                        Rank {fn.rank}
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* Per-File Maintainability Index */}
      <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
        <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-4">
          Per-File Maintainability Index (MI)
        </h3>
        <div className="space-y-3">
          {results
            .filter((r) => !r.error)
            .slice(0, 15)
            .map((r, idx) => {
              const fname = r.filepath.split(/[/\\]/).pop();
              const color =
                r.mi_score >= 65
                  ? 'bg-emerald-500'
                  : r.mi_score >= 35
                  ? 'bg-amber-500'
                  : 'bg-rose-500';
              return (
                <div key={idx} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-mono text-slate-800 dark:text-slate-200 truncate">
                      {fname}
                    </span>
                    <span className="font-medium text-slate-600 dark:text-slate-300">
                      MI: {r.mi_score} [{r.mi_rank}] • max CC: {r.max_cc}
                    </span>
                  </div>
                  <div className="w-full bg-slate-100 dark:bg-slate-800 rounded-full h-2 overflow-hidden">
                    <div
                      className={`h-full rounded-full ${color}`}
                      style={{ width: `${Math.min(100, Math.max(0, r.mi_score))}%` }}
                    ></div>
                  </div>
                </div>
              );
            })}
        </div>
      </div>
    </div>
  );
};
