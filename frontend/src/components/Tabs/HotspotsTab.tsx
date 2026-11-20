import React, { useState } from 'react';
import { HotspotsData } from '../../types/analysis';
import { StatusBadge } from '../StatusBadge';
import { ChevronDown, ChevronUp, Search, Flame, Code } from 'lucide-react';

interface HotspotsTabProps {
  data: HotspotsData;
}

export const HotspotsTab: React.FC<HotspotsTabProps> = ({ data }) => {
  const [filterTier, setFilterTier] = useState<string>('ALL');
  const [search, setSearch] = useState<string>('');
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [sortField, setSortField] = useState<string>('risk_score');
  const [sortAsc, setSortAsc] = useState<boolean>(false);

  const { hotspots, summary } = data;

  const filtered = hotspots.filter((h) => {
    const matchesTier =
      filterTier === 'ALL' ||
      h.risk_tier.toLowerCase().includes(filterTier.toLowerCase());
    const matchesSearch =
      !search || h.rel_path.toLowerCase().includes(search.toLowerCase());
    return matchesTier && matchesSearch;
  });

  filtered.sort((a, b) => {
    let valA = (a as any)[sortField];
    let valB = (b as any)[sortField];
    if (typeof valA === 'string') {
      return sortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
    }
    return sortAsc ? valA - valB : valB - valA;
  });

  const handleSort = (field: string) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Summary KPI Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
          <p className="text-xs text-slate-500">Files Scored</p>
          <p className="text-xl font-bold mt-1">{summary.total_files_scored}</p>
        </div>
        <div className="p-4 rounded-xl border border-rose-200 dark:border-rose-900/50 bg-rose-50/40 dark:bg-rose-950/20">
          <p className="text-xs text-rose-700 dark:text-rose-400 font-medium">Critical Risk</p>
          <p className="text-xl font-bold text-rose-700 dark:text-rose-400 mt-1">
            {summary.critical_count}
          </p>
        </div>
        <div className="p-4 rounded-xl border border-orange-200 dark:border-orange-900/50 bg-orange-50/40 dark:bg-orange-950/20">
          <p className="text-xs text-orange-700 dark:text-orange-400 font-medium">High Risk</p>
          <p className="text-xl font-bold text-orange-700 dark:text-orange-400 mt-1">
            {summary.high_count}
          </p>
        </div>
        <div className="p-4 rounded-xl border border-amber-200 dark:border-amber-900/50 bg-amber-50/40 dark:bg-amber-950/20">
          <p className="text-xs text-amber-700 dark:text-amber-400 font-medium">Medium Risk</p>
          <p className="text-xl font-bold text-amber-700 dark:text-amber-400 mt-1">
            {summary.medium_count}
          </p>
        </div>
        <div className="p-4 rounded-xl border border-emerald-200 dark:border-emerald-900/50 bg-emerald-50/40 dark:bg-emerald-950/20">
          <p className="text-xs text-emerald-700 dark:text-emerald-400 font-medium">Low Risk</p>
          <p className="text-xl font-bold text-emerald-700 dark:text-emerald-400 mt-1">
            {summary.low_count}
          </p>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search hotspots by file path..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-sm rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
          {['ALL', 'Critical', 'High', 'Medium', 'Low'].map((tier) => (
            <button
              key={tier}
              onClick={() => setFilterTier(tier)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors ${
                filterTier === tier
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800'
              }`}
            >
              {tier}
            </button>
          ))}
        </div>
      </div>

      {/* Hotspots Table */}
      <div className="border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden bg-white dark:bg-slate-900 shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs sm:text-sm">
            <thead className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400 font-medium">
              <tr>
                <th className="py-3 px-4 cursor-pointer" onClick={() => handleSort('risk_tier')}>
                  Tier
                </th>
                <th className="py-3 px-4 cursor-pointer" onClick={() => handleSort('rel_path')}>
                  File Path
                </th>
                <th className="py-3 px-4 text-right cursor-pointer" onClick={() => handleSort('risk_score')}>
                  Risk Score
                </th>
                <th className="py-3 px-4 text-right cursor-pointer" onClick={() => handleSort('commit_count')}>
                  Commits
                </th>
                <th className="py-3 px-4 text-right cursor-pointer" onClick={() => handleSort('max_cc')}>
                  Max CC
                </th>
                <th className="py-3 px-4 text-right cursor-pointer" onClick={() => handleSort('mi_score')}>
                  MI Score
                </th>
                <th className="py-3 px-4 text-right cursor-pointer" onClick={() => handleSort('author_count')}>
                  Authors
                </th>
                <th className="py-3 px-4 text-center">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-slate-400">
                    No hotspot files match the selected filter.
                  </td>
                </tr>
              ) : (
                filtered.map((item) => {
                  const isExpanded = expandedRow === item.rel_path;
                  return (
                    <React.Fragment key={item.rel_path}>
                      <tr className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors">
                        <td className="py-3 px-4">
                          <StatusBadge status={item.risk_tier} size="sm" />
                        </td>
                        <td className="py-3 px-4 font-mono text-xs text-slate-900 dark:text-slate-200">
                          {item.rel_path}
                        </td>
                        <td className="py-3 px-4 text-right font-bold text-slate-900 dark:text-white">
                          {item.risk_score.toFixed(4)}
                        </td>
                        <td className="py-3 px-4 text-right text-slate-600 dark:text-slate-300">
                          {item.commit_count}
                        </td>
                        <td className="py-3 px-4 text-right font-medium text-slate-700 dark:text-slate-300">
                          {item.max_cc}
                        </td>
                        <td className="py-3 px-4 text-right text-slate-600 dark:text-slate-300">
                          {item.mi_score.toFixed(1)} [{item.mi_rank}]
                        </td>
                        <td className="py-3 px-4 text-right text-slate-600 dark:text-slate-300">
                          {item.author_count}
                        </td>
                        <td className="py-3 px-4 text-center">
                          <button
                            onClick={() => setExpandedRow(isExpanded ? null : item.rel_path)}
                            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                            title="Toggle details"
                          >
                            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                          </button>
                        </td>
                      </tr>

                      {/* Expanded Row Drawer */}
                      {isExpanded && (
                        <tr className="bg-blue-50/30 dark:bg-blue-950/10 border-b border-slate-200 dark:border-slate-800">
                          <td colSpan={8} className="p-4">
                            <div className="bg-white dark:bg-slate-900 rounded-xl p-4 border border-slate-200 dark:border-slate-800 space-y-3">
                              <div className="flex items-center justify-between">
                                <h4 className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                                  <Flame className="w-3.5 h-3.5 text-orange-500" />
                                  Diagnostic Breakdown: {item.rel_path}
                                </h4>
                                <span className="text-xs text-slate-400">
                                  Last Changed: {item.last_changed || 'N/A'}
                                </span>
                              </div>

                              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                                <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800">
                                  <span className="text-slate-400">Churn Rate</span>
                                  <p className="font-semibold text-slate-800 dark:text-slate-200 mt-0.5">
                                    {item.churn_rate} commits / 30d
                                  </p>
                                </div>
                                <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800">
                                  <span className="text-slate-400">Average Complexity</span>
                                  <p className="font-semibold text-slate-800 dark:text-slate-200 mt-0.5">
                                    {item.avg_cc} avg CC
                                  </p>
                                </div>
                                <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800">
                                  <span className="text-slate-400">Maintainability Index</span>
                                  <p className="font-semibold text-slate-800 dark:text-slate-200 mt-0.5">
                                    {item.mi_score} / 100 ({item.mi_rank})
                                  </p>
                                </div>
                                <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800">
                                  <span className="text-slate-400">Authors In Git</span>
                                  <p className="font-semibold text-slate-800 dark:text-slate-200 mt-0.5">
                                    {item.author_count} contributors
                                  </p>
                                </div>
                              </div>

                              {item.hotspot_fn && (
                                <div className="p-2.5 rounded-lg bg-rose-50/50 dark:bg-rose-950/20 border border-rose-200/60 dark:border-rose-900/40 flex items-center gap-2">
                                  <Code className="w-4 h-4 text-rose-500 shrink-0" />
                                  <span className="text-xs text-rose-800 dark:text-rose-300">
                                    Most complex routine: <code className="font-bold">{item.hotspot_fn}()</code> (Max CC = {item.max_cc})
                                  </span>
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
