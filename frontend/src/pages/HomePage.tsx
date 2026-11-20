import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Search,
  Sparkles,
  ArrowRight,
  History,
  Clock,
  AlertCircle,
} from 'lucide-react';
import { api } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';

export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const [url, setUrl] = useState<string>('');
  const [topN, setTopN] = useState<number>(10);
  const [force, setForce] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [inputError, setInputError] = useState<string | null>(null);

  const { data: recentAnalyses, isLoading: recentLoading } = useQuery({
    queryKey: ['recentAnalyses'],
    queryFn: () => api.listAnalyses(1, 6),
  });

  const validateUrl = (input: string): boolean => {
    const clean = input.trim();
    if (!clean) {
      setInputError('Please enter a GitHub repository URL.');
      return false;
    }
    const pattern = /^https:\/\/github\.com\/([A-Za-z0-9_.-]+)\/([A-Za-z0-9_.-]+?)(?:\.git)?\/?$/;
    if (!pattern.test(clean)) {
      setInputError('URL must be a public repository: https://github.com/<owner>/<repo>');
      return false;
    }
    setInputError(null);
    return true;
  };

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!validateUrl(url)) return;

    setLoading(true);
    setInputError(null);

    try {
      const res = await api.createAnalysis(url.trim(), topN, force);
      navigate(`/analyses/${res.id}`);
    } catch (err: any) {
      setInputError(err.message || 'Failed to initiate analysis job');
    } finally {
      setLoading(false);
    }
  };

  const handleChipClick = (exampleUrl: string) => {
    setUrl(exampleUrl);
    setInputError(null);
  };

  return (
    <div className="space-y-12">
      {/* Hero Section */}
      <div className="text-center max-w-3xl mx-auto space-y-4 pt-4">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-400 border border-blue-200 dark:border-blue-900">
          <Sparkles className="w-3.5 h-3.5" />
          Production-Grade Full-Stack Profiler
        </div>
        <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900 dark:text-white">
          Automated Code Complexity, Churn &amp; Architecture Profiler
        </h2>
        <p className="text-sm sm:text-base text-slate-600 dark:text-slate-400">
          Programmatically clone any public repository. Compute Radon Cyclomatic Complexity, AST dependency graphs, git churn, and risk hotspots backed by OpenRouter LLM insights.
        </p>
      </div>

      {/* Input Box Card */}
      <div className="max-w-2xl mx-auto bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl p-6 sm:p-8 shadow-sm">
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label
              htmlFor="github-url-input"
              className="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-2"
            >
              GitHub Repository URL
            </label>
            <div className="relative">
              <Search className="w-5 h-5 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                id="github-url-input"
                type="text"
                value={url}
                onChange={(e) => {
                  setUrl(e.target.value);
                  if (inputError) setInputError(null);
                }}
                placeholder="https://github.com/pallets/markupsafe"
                className={`w-full pl-11 pr-4 py-3 rounded-xl border text-sm font-mono bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-2 ${
                  inputError
                    ? 'border-rose-400 focus:ring-rose-500'
                    : 'border-slate-200 dark:border-slate-700 focus:ring-blue-500'
                }`}
              />
            </div>
            {inputError && (
              <p className="mt-2 text-xs text-rose-600 dark:text-rose-400 flex items-center gap-1">
                <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                {inputError}
              </p>
            )}
          </div>

          {/* Settings Row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
            <div>
              <div className="flex justify-between text-xs text-slate-500 mb-1.5 font-medium">
                <span>Top Hotspots to Rank</span>
                <span className="font-bold text-slate-900 dark:text-white">{topN}</span>
              </div>
              <input
                type="range"
                min="5"
                max="50"
                step="5"
                value={topN}
                onChange={(e) => setTopN(parseInt(e.target.value, 10))}
                className="w-full accent-blue-600 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-lg cursor-pointer"
              />
            </div>

            <div className="flex items-center sm:justify-end gap-2 pt-2">
              <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-600 dark:text-slate-300">
                <input
                  type="checkbox"
                  checked={force}
                  onChange={(e) => setForce(e.target.checked)}
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 w-4 h-4"
                />
                Force Re-analyse (Bypass 24h cache)
              </label>
            </div>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3.5 px-6 rounded-xl font-bold text-sm bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white shadow-sm shadow-blue-500/25 transition-all flex items-center justify-center gap-2 group"
          >
            {loading ? (
              'Initiating Analysis...'
            ) : (
              <>
                <span>🚀 Launch Repository Analysis</span>
                <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </>
            )}
          </button>
        </form>

        {/* Example Chips */}
        <div className="mt-6 pt-6 border-t border-slate-100 dark:border-slate-800">
          <p className="text-xs font-semibold text-slate-400 mb-2.5">
            Quick-start with demo repositories:
          </p>
          <div className="flex flex-wrap gap-2">
            {[
              { name: 'markupsafe', url: 'https://github.com/pallets/markupsafe', desc: 'Small & Fast' },
              { name: 'flask', url: 'https://github.com/pallets/flask', desc: 'Medium & Modular' },
              { name: 'requests', url: 'https://github.com/psf/requests', desc: 'Complex Hotspots' },
            ].map((repo) => (
              <button
                key={repo.name}
                type="button"
                onClick={() => handleChipClick(repo.url)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium border border-slate-200 dark:border-slate-800 hover:border-blue-400 hover:bg-blue-50 dark:hover:bg-blue-950/40 text-slate-700 dark:text-slate-300 transition-colors flex items-center gap-1.5"
              >
                <span>{repo.name}</span>
                <span className="text-[10px] text-slate-400">({repo.desc})</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Recent Analyses Grid */}
      <div className="max-w-5xl mx-auto space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-500 flex items-center gap-2">
            <History className="w-4 h-4" />
            Recent Analyses
          </h3>
          <Link
            to="/history"
            className="text-xs font-semibold text-blue-600 dark:text-blue-400 hover:underline"
          >
            View All History →
          </Link>
        </div>

        {recentLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-28 rounded-2xl bg-slate-200 dark:bg-slate-800 animate-pulse"></div>
            ))}
          </div>
        ) : recentAnalyses && recentAnalyses.items.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {recentAnalyses.items.map((item) => (
              <Link
                key={item.id}
                to={`/analyses/${item.id}`}
                className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-blue-300 dark:hover:border-blue-800 hover:shadow-md transition-all space-y-3"
              >
                <div className="flex items-start justify-between">
                  <h4 className="font-bold text-slate-900 dark:text-white truncate">
                    {item.repo_name}
                  </h4>
                  <StatusBadge status={item.status} size="sm" />
                </div>
                <div className="text-xs text-slate-500 space-y-1">
                  <p className="truncate font-mono text-[11px]">{item.github_url}</p>
                  {item.key_metrics && (
                    <p className="text-[11px] text-slate-600 dark:text-slate-300 flex items-center gap-2">
                      <span>{item.key_metrics.total_files} files</span>
                      <span>•</span>
                      <span>{item.key_metrics.total_commits} commits</span>
                      <span>•</span>
                      <span className="text-rose-500 font-semibold">
                        {item.key_metrics.critical_hotspots} critical
                      </span>
                    </p>
                  )}
                </div>
                <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {new Date(item.created_at).toLocaleDateString()}
                  </span>
                  <span>{item.duration_seconds ? `${item.duration_seconds}s` : ''}</span>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <div className="p-8 text-center text-slate-400 border border-dashed border-slate-200 dark:border-slate-800 rounded-2xl">
            No analyses recorded yet. Paste a GitHub repository above to start!
          </div>
        )}
      </div>
    </div>
  );
};
