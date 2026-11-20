import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Search,
  Trash2,
  ExternalLink,
  RotateCcw,
  FileSpreadsheet,
  Filter,
} from 'lucide-react';
import { api } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';

export const HistoryPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [page, setPage] = useState<number>(1);
  const [search, setSearch] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');

  const { data, isLoading } = useQuery({
    queryKey: ['analysesHistory', page, search, statusFilter],
    queryFn: () => api.listAnalyses(page, 15, search || undefined, statusFilter || undefined),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteAnalysis(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['analysesHistory'] });
      queryClient.invalidateQueries({ queryKey: ['recentAnalyses'] });
    },
  });

  const handleDelete = (id: string, name: string) => {
    if (confirm(`Are you sure you want to delete analysis for '${name}'?`)) {
      deleteMutation.mutate(id);
    }
  };

  const handleRerun = async (githubUrl: string) => {
    try {
      const res = await api.createAnalysis(githubUrl, 10, true);
      navigate(`/analyses/${res.id}`);
    } catch (err: any) {
      alert(`Re-run failed: ${err.message}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-extrabold text-slate-900 dark:text-white tracking-tight">
            Analysis History
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Search, review, export, and manage past repository analyses.
          </p>
        </div>

        <Link
          to="/"
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold transition-colors"
        >
          + Analyse New Repo
        </Link>
      </div>

      {/* Search and Filters */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search by repo or URL..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="w-full pl-9 pr-4 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            aria-label="Filter analyses by status"
            className="px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-300 focus:outline-none"
          >
            <option value="">All Statuses</option>
            <option value="completed">Completed</option>
            <option value="running">Running</option>
            <option value="queued">Queued</option>
            <option value="failed">Failed</option>
          </select>
        </div>
      </div>

      {/* History Table */}
      <div className="border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden bg-white dark:bg-slate-900 shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs sm:text-sm">
            <thead className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400 font-medium">
              <tr>
                <th className="py-3 px-4">Repository</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">LOC</th>
                <th className="py-3 px-4 text-right">Commits</th>
                <th className="py-3 px-4 text-right">Avg MI</th>
                <th className="py-3 px-4 text-right">Critical Risk</th>
                <th className="py-3 px-4">Date</th>
                <th className="py-3 px-4 text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
              {isLoading ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-400">
                    Loading analysis history...
                  </td>
                </tr>
              ) : !data || data.items.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-400">
                    No matching analyses found.
                  </td>
                </tr>
              ) : (
                data.items.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors">
                    <td className="py-3.5 px-4">
                      <div>
                        <Link
                          to={`/analyses/${item.id}`}
                          className="font-bold text-slate-900 dark:text-white hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
                        >
                          {item.repo_name}
                        </Link>
                        <p className="text-[11px] font-mono text-slate-400 truncate max-w-xs">
                          {item.github_url}
                        </p>
                      </div>
                    </td>
                    <td className="py-3.5 px-4">
                      <StatusBadge status={item.status} size="sm" />
                    </td>
                    <td className="py-3.5 px-4 text-right text-slate-600 dark:text-slate-300">
                      {item.key_metrics ? item.key_metrics.total_loc.toLocaleString() : '—'}
                    </td>
                    <td className="py-3.5 px-4 text-right text-slate-600 dark:text-slate-300">
                      {item.key_metrics ? item.key_metrics.total_commits.toLocaleString() : '—'}
                    </td>
                    <td className="py-3.5 px-4 text-right font-medium text-slate-700 dark:text-slate-300">
                      {item.key_metrics ? `${item.key_metrics.avg_mi_score}/100` : '—'}
                    </td>
                    <td className="py-3.5 px-4 text-right font-bold text-rose-600 dark:text-rose-400">
                      {item.key_metrics ? item.key_metrics.critical_hotspots : '—'}
                    </td>
                    <td className="py-3.5 px-4 text-slate-500 dark:text-slate-400 text-xs whitespace-nowrap">
                      {new Date(item.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3.5 px-4 text-center">
                      <div className="flex items-center justify-center gap-1.5">
                        <Link
                          to={`/analyses/${item.id}`}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-blue-600 hover:bg-slate-100 dark:hover:bg-slate-800"
                          title="Open Dashboard"
                        >
                          <ExternalLink className="w-4 h-4" />
                        </Link>
                        {item.status === 'completed' && (
                          <a
                            href={api.getReportPdfUrl(item.id)}
                            download={`${item.repo_name}_report.pdf`}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-slate-100 dark:hover:bg-slate-800"
                            title="Download PDF"
                          >
                            <FileSpreadsheet className="w-4 h-4" />
                          </a>
                        )}
                        <button
                          onClick={() => handleRerun(item.github_url)}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-emerald-600 hover:bg-slate-100 dark:hover:bg-slate-800"
                          title="Re-run Analysis"
                        >
                          <RotateCcw className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(item.id, item.repo_name)}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-slate-100 dark:hover:bg-slate-800"
                          title="Delete Analysis"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        {data && data.pages > 1 && (
          <div className="p-4 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between text-xs text-slate-500">
            <span>
              Showing Page {data.page} of {data.pages} ({data.total} total)
            </span>
            <div className="flex items-center gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
                className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 disabled:opacity-40 hover:bg-slate-50 dark:hover:bg-slate-800"
              >
                Previous
              </button>
              <button
                disabled={page >= data.pages}
                onClick={() => setPage(page + 1)}
                className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 disabled:opacity-40 hover:bg-slate-50 dark:hover:bg-slate-800"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
