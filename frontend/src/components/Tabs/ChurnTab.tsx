import React, { useState } from 'react';
import { ChurnData } from '../../types/analysis';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { Calendar, GitCommit, Users, Clock, Search } from 'lucide-react';

interface ChurnTabProps {
  data: ChurnData;
}

export const ChurnTab: React.FC<ChurnTabProps> = ({ data }) => {
  const { stats, most_churned, file_churn } = data;
  const [search, setSearch] = useState<string>('');

  const chartData = most_churned.map((f) => ({
    name: f.rel_path.split(/[/\\]/).pop() || f.rel_path,
    commits: f.commit_count,
    fullPath: f.rel_path,
  }));

  const allFiles = Object.values(file_churn)
    .filter((f) => !search || f.rel_path.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => b.commit_count - a.commit_count);

  const maxCommits = Math.max(...Object.values(file_churn).map((f) => f.commit_count), 1);

  return (
    <div className="space-y-6">
      {/* Timeline Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
          <div className="flex items-center gap-1.5 text-slate-500 text-xs font-medium">
            <GitCommit className="w-3.5 h-3.5" />
            Total Commits
          </div>
          <p className="text-xl font-bold mt-1 text-slate-900 dark:text-white">
            {stats.total_commits.toLocaleString()}
          </p>
        </div>
        <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
          <div className="flex items-center gap-1.5 text-slate-500 text-xs font-medium">
            <Users className="w-3.5 h-3.5" />
            Contributors
          </div>
          <p className="text-xl font-bold mt-1 text-slate-900 dark:text-white">
            {stats.total_authors}
          </p>
        </div>
        <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
          <div className="flex items-center gap-1.5 text-slate-500 text-xs font-medium">
            <Clock className="w-3.5 h-3.5" />
            Repository Age
          </div>
          <p className="text-xl font-bold mt-1 text-slate-900 dark:text-white">
            {stats.repo_age_days} days
          </p>
        </div>
        <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
          <div className="flex items-center gap-1.5 text-slate-500 text-xs font-medium">
            <Calendar className="w-3.5 h-3.5" />
            First Commit
          </div>
          <p className="text-sm font-bold mt-1 text-slate-900 dark:text-white">
            {stats.first_commit}
          </p>
        </div>
        <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
          <div className="flex items-center gap-1.5 text-slate-500 text-xs font-medium">
            <Calendar className="w-3.5 h-3.5" />
            Last Commit
          </div>
          <p className="text-sm font-bold mt-1 text-slate-900 dark:text-white">
            {stats.last_commit}
          </p>
        </div>
      </div>

      {/* Most Churned Chart */}
      <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
        <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-4">
          Most Churned Files (Top Commit Activity)
        </h3>
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
              <XAxis dataKey="name" tick={{ fontSize: 11 }} angle={-25} textAnchor="end" stroke="#94a3b8" />
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
              <Bar dataKey="commits" fill="#3b82f6" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Per-File Churn Table */}
      <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <h3 className="text-sm font-bold text-slate-900 dark:text-white">
            All Tracked Files Churn Detail
          </h3>
          <div className="relative w-full sm:w-64">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Filter files..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
        </div>

        <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
          {allFiles.map((f) => (
            <div
              key={f.rel_path}
              className="p-3 rounded-xl border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 space-y-2"
            >
              <div className="flex items-center justify-between text-xs">
                <span className="font-mono font-medium text-slate-800 dark:text-slate-200 truncate">
                  {f.rel_path}
                </span>
                <span className="text-slate-500 shrink-0">
                  {f.commit_count} commits • {f.author_count} author(s) • last: {f.last_changed || 'never'}
                </span>
              </div>
              <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-1.5 overflow-hidden">
                <div
                  className="bg-blue-600 dark:bg-blue-500 h-full rounded-full"
                  style={{ width: `${(f.commit_count / maxCommits) * 100}%` }}
                ></div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
