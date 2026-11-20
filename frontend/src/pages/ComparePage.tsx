import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { GitCompare, Flame } from 'lucide-react';
import { api } from '../api/client';
import { AnalysisDetail } from '../types/analysis';

export const ComparePage: React.FC = () => {
  const [leftId, setLeftId] = useState<string>('');
  const [rightId, setRightId] = useState<string>('');

  const { data: historyData } = useQuery({
    queryKey: ['analysesCompareList'],
    queryFn: () => api.listAnalyses(1, 100, undefined, 'completed'),
  });

  const { data: leftAnalysis } = useQuery<AnalysisDetail>({
    queryKey: ['analysis', leftId],
    queryFn: () => api.getAnalysis(leftId),
    enabled: !!leftId,
  });

  const { data: rightAnalysis } = useQuery<AnalysisDetail>({
    queryKey: ['analysis', rightId],
    queryFn: () => api.getAnalysis(rightId),
    enabled: !!rightId,
  });

  const completedList = historyData?.items || [];

  const leftRes = leftAnalysis?.result;
  const rightRes = rightAnalysis?.result;

  const renderMetricDiff = (
    label: string,
    val1: number,
    val2: number,
    higherIsBetter: boolean = true,
    suffix: string = ''
  ) => {
    const diff = val2 - val1;
    let color = 'text-slate-500';
    if (diff !== 0) {
      if (higherIsBetter) {
        color = diff > 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400';
      } else {
        color = diff < 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400';
      }
    }

    return (
      <tr className="border-b border-slate-100 dark:border-slate-800 text-xs">
        <td className="py-3 px-4 font-semibold text-slate-700 dark:text-slate-300">
          {label}
        </td>
        <td className="py-3 px-4 text-right font-bold text-slate-900 dark:text-white">
          {val1.toLocaleString()}{suffix}
        </td>
        <td className="py-3 px-4 text-right font-bold text-slate-900 dark:text-white">
          {val2.toLocaleString()}{suffix}
        </td>
        <td className={`py-3 px-4 text-right font-bold ${color}`}>
          {diff > 0 ? `+${diff.toLocaleString()}` : diff.toLocaleString()}{suffix}
        </td>
      </tr>
    );
  };

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div>
        <h2 className="text-2xl font-extrabold text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
          <GitCompare className="w-6 h-6 text-blue-600" />
          Repository Comparison
        </h2>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
          Select two completed repository profiles to compare architecture, static complexity, and hotspot density.
        </p>
      </div>

      {/* Selectors Bar */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
        <div>
          <label
            htmlFor="baseline-repo-select"
            className="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-2"
          >
            Baseline Repository (Left)
          </label>
          <select
            id="baseline-repo-select"
            value={leftId}
            onChange={(e) => setLeftId(e.target.value)}
            className="w-full px-3 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white text-xs font-medium focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">Select baseline repository...</option>
            {completedList.map((item) => (
              <option key={item.id} value={item.id}>
                {item.repo_name} ({new Date(item.created_at).toLocaleDateString()})
              </option>
            ))}
          </select>
        </div>

        <div>
          <label
            htmlFor="target-repo-select"
            className="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-2"
          >
            Comparison Target (Right)
          </label>
          <select
            id="target-repo-select"
            value={rightId}
            onChange={(e) => setRightId(e.target.value)}
            className="w-full px-3 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white text-xs font-medium focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">Select target repository...</option>
            {completedList.map((item) => (
              <option key={item.id} value={item.id}>
                {item.repo_name} ({new Date(item.created_at).toLocaleDateString()})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Side-by-Side Cards */}
      {leftRes && rightRes ? (
        <div className="space-y-6">
          <div className="border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden bg-white dark:bg-slate-900 shadow-sm">
            <div className="p-4 bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800">
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                Architectural Metrics Matrix
              </h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead className="bg-slate-50/50 dark:bg-slate-800/30 text-xs font-medium text-slate-400 border-b border-slate-100 dark:border-slate-800">
                  <tr>
                    <th className="py-2.5 px-4">Metric</th>
                    <th className="py-2.5 px-4 text-right font-bold text-blue-600 dark:text-blue-400">
                      {leftAnalysis.repo_name}
                    </th>
                    <th className="py-2.5 px-4 text-right font-bold text-indigo-600 dark:text-indigo-400">
                      {rightAnalysis.repo_name}
                    </th>
                    <th className="py-2.5 px-4 text-right">Delta (Right - Left)</th>
                  </tr>
                </thead>
                <tbody>
                  {renderMetricDiff(
                    'Total Files',
                    leftRes.manifest.total_files,
                    rightRes.manifest.total_files,
                    false
                  )}
                  {renderMetricDiff(
                    'Lines of Code (LOC)',
                    leftRes.manifest.total_loc,
                    rightRes.manifest.total_loc,
                    false
                  )}
                  {renderMetricDiff(
                    'Total Commits',
                    leftRes.churn.stats.total_commits,
                    rightRes.churn.stats.total_commits,
                    true
                  )}
                  {renderMetricDiff(
                    'Active Authors',
                    leftRes.churn.stats.total_authors,
                    rightRes.churn.stats.total_authors,
                    true
                  )}
                  {renderMetricDiff(
                    'Repo Age (Days)',
                    leftRes.churn.stats.repo_age_days,
                    rightRes.churn.stats.repo_age_days,
                    true
                  )}
                  {renderMetricDiff(
                    'Avg Maintainability (MI)',
                    leftRes.complexity.summary.avg_mi_score,
                    rightRes.complexity.summary.avg_mi_score,
                    true,
                    ' / 100'
                  )}
                  {renderMetricDiff(
                    'Low MI Files (<20)',
                    leftRes.complexity.summary.low_mi_file_count,
                    rightRes.complexity.summary.low_mi_file_count,
                    false
                  )}
                  {renderMetricDiff(
                    'AST Circular Dependencies',
                    leftRes.graph.stats.cycle_count,
                    rightRes.graph.stats.cycle_count,
                    false
                  )}
                  {renderMetricDiff(
                    'Critical Risk Hotspots',
                    leftRes.hotspots.summary.critical_count,
                    rightRes.hotspots.summary.critical_count,
                    false
                  )}
                  {renderMetricDiff(
                    'High Risk Hotspots',
                    leftRes.hotspots.summary.high_count,
                    rightRes.hotspots.summary.high_count,
                    false
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Top Hotspots Comparison */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-3">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                <Flame className="w-4 h-4 text-orange-500" />
                {leftAnalysis.repo_name} — Top Hotspots
              </h4>
              <div className="space-y-2">
                {leftRes.hotspots.top_hotspots.slice(0, 5).map((h, idx) => (
                  <div
                    key={idx}
                    className="p-2.5 rounded-xl border border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/40 flex items-center justify-between text-xs"
                  >
                    <span className="font-mono text-slate-800 dark:text-slate-200 truncate max-w-xs">
                      {h.rel_path}
                    </span>
                    <span className="font-bold text-rose-600 dark:text-rose-400">
                      Risk {h.risk_score.toFixed(4)}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-3">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                <Flame className="w-4 h-4 text-orange-500" />
                {rightAnalysis.repo_name} — Top Hotspots
              </h4>
              <div className="space-y-2">
                {rightRes.hotspots.top_hotspots.slice(0, 5).map((h, idx) => (
                  <div
                    key={idx}
                    className="p-2.5 rounded-xl border border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/40 flex items-center justify-between text-xs"
                  >
                    <span className="font-mono text-slate-800 dark:text-slate-200 truncate max-w-xs">
                      {h.rel_path}
                    </span>
                    <span className="font-bold text-rose-600 dark:text-rose-400">
                      Risk {h.risk_score.toFixed(4)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="p-12 text-center text-slate-400 border border-dashed border-slate-200 dark:border-slate-800 rounded-2xl">
          Please select two completed repositories from the dropdowns above to compare.
        </div>
      )}
    </div>
  );
};
