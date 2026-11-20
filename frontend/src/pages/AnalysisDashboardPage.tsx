import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ExternalLink,
  Calendar,
  Clock,
  Activity,
  Network,
  Layers,
  FileCode2,
  GitCommit,
  AlertCircle,
} from 'lucide-react';
import { api } from '../api/client';
import { AnalysisDetail, AnalysisEvent } from '../types/analysis';
import { StatusBadge } from '../components/StatusBadge';
import { KpiCard } from '../components/KpiCard';
import { ProgressStepper } from '../components/ProgressStepper';
import { HotspotsTab } from '../components/Tabs/HotspotsTab';
import { ComplexityTab } from '../components/Tabs/ComplexityTab';
import { DependencyGraphTab } from '../components/Tabs/DependencyGraphTab';
import { ChurnTab } from '../components/Tabs/ChurnTab';
import { AiReportTab } from '../components/Tabs/AiReportTab';

export const AnalysisDashboardPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<'hotspots' | 'complexity' | 'graph' | 'churn' | 'report'>('hotspots');
  const [liveEvent, setLiveEvent] = useState<AnalysisEvent | null>(null);

  const {
    data: analysis,
    isLoading,
    error,
    refetch,
  } = useQuery<AnalysisDetail>({
    queryKey: ['analysis', id],
    queryFn: () => api.getAnalysis(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && (data.status === 'queued' || data.status === 'running')) {
        return 2000;
      }
      return false;
    },
  });

  // Subscribe to SSE stream while analysis is not terminal
  useEffect(() => {
    if (!id) return;
    if (analysis && (analysis.status === 'completed' || analysis.status === 'failed')) {
      return;
    }

    const unsubscribe = api.subscribeToEvents(
      id,
      (event) => {
        setLiveEvent(event);
        if (event.status === 'completed' || event.status === 'failed') {
          queryClient.invalidateQueries({ queryKey: ['analysis', id] });
          refetch();
        }
      },
      (err) => {
        console.warn('SSE connection warning', err);
      }
    );

    return () => {
      unsubscribe();
    };
  }, [id, analysis?.status, queryClient, refetch]);

  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-28 rounded-2xl bg-slate-200 dark:bg-slate-800"></div>
        <div className="grid grid-cols-1 sm:grid-cols-5 gap-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-24 rounded-2xl bg-slate-200 dark:bg-slate-800"></div>
          ))}
        </div>
      </div>
    );
  }

  if (error || !analysis) {
    return (
      <div className="max-w-xl mx-auto text-center py-16 space-y-4">
        <div className="w-12 h-12 rounded-full bg-rose-100 dark:bg-rose-950/60 text-rose-600 flex items-center justify-center mx-auto">
          <AlertCircle className="w-6 h-6" />
        </div>
        <h3 className="text-lg font-bold text-slate-900 dark:text-white">Analysis Not Found</h3>
        <p className="text-xs text-slate-500">
          {(error as any)?.message || `We couldn't retrieve analysis '${id}'.`}
        </p>
        <button
          onClick={() => navigate('/')}
          className="px-4 py-2 bg-blue-600 text-white rounded-xl text-xs font-semibold hover:bg-blue-700"
        >
          Return Home
        </button>
      </div>
    );
  }

  const isWorking = analysis.status === 'queued' || analysis.status === 'running';
  const isFailed = analysis.status === 'failed';
  const isCompleted = analysis.status === 'completed';

  const currentPercent = liveEvent ? liveEvent.percent : analysis.percent;
  const currentStage = liveEvent ? liveEvent.stage : analysis.stage;
  const currentMessage = liveEvent ? liveEvent.message : analysis.stage ? `Stage: ${analysis.stage}` : 'Initializing...';
  const currentError = liveEvent?.error || analysis.error;

  const result = analysis.result;

  const handleRetry = async () => {
    try {
      const res = await api.createAnalysis(analysis.github_url, 10, true);
      navigate(`/analyses/${res.id}`);
    } catch (err: any) {
      alert(`Retry failed: ${err.message}`);
    }
  };

  return (
    <div className="space-y-8">
      {/* Repository Header */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl p-6 sm:p-8 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-3 flex-wrap">
              <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">
                {analysis.repo_name}
              </h2>
              <StatusBadge status={analysis.status} />
              {analysis.report_status === 'failed' && (
                <span className="text-[11px] font-semibold text-amber-600 bg-amber-50 dark:bg-amber-950/60 border border-amber-200 dark:border-amber-900 px-2 py-0.5 rounded-full">
                  AI Report Failed
                </span>
              )}
            </div>

            <div className="flex items-center gap-4 text-xs text-slate-500 dark:text-slate-400 flex-wrap">
              <a
                href={analysis.github_url}
                target="_blank"
                rel="noopener noreferrer"
                className="font-mono text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1"
              >
                {analysis.github_url}
                <ExternalLink className="w-3.5 h-3.5" />
              </a>

              {result?.churn?.stats && (
                <>
                  <span>•</span>
                  <span>{result.churn.stats.total_commits.toLocaleString()} commits</span>
                  <span>•</span>
                  <span>{result.churn.stats.total_authors} contributors</span>
                  <span>•</span>
                  <span>{result.churn.stats.repo_age_days} days active</span>
                </>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3 text-xs text-slate-400 shrink-0">
            <div className="flex items-center gap-1.5">
              <Clock className="w-4 h-4" />
              <span>{analysis.duration_seconds ? `${analysis.duration_seconds}s execution` : 'In progress'}</span>
            </div>
            <span>•</span>
            <div className="flex items-center gap-1.5">
              <Calendar className="w-4 h-4" />
              <span>{new Date(analysis.created_at).toLocaleDateString()}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Live Stepper View when in progress or failed */}
      {(isWorking || isFailed) && (
        <ProgressStepper
          currentStage={currentStage}
          percent={currentPercent}
          message={currentMessage}
          status={liveEvent ? liveEvent.status : analysis.status}
          error={currentError}
          onRetry={handleRetry}
        />
      )}

      {/* Completed Dashboard */}
      {isCompleted && result && (
        <>
          {/* KPI Cards Row */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
            <KpiCard
              title="Total Files"
              value={result.manifest.total_files}
              subtitle={`${result.manifest.total_python_files || result.manifest.python_files.length} Python`}
              icon={<FileCode2 className="w-5 h-5" />}
            />
            <KpiCard
              title="Lines of Code"
              value={result.manifest.total_loc.toLocaleString()}
              subtitle="Non-empty LOC"
              icon={<Layers className="w-5 h-5" />}
            />
            <KpiCard
              title="Total Commits"
              value={result.churn.stats.total_commits.toLocaleString()}
              subtitle={`${result.churn.stats.total_authors} authors`}
              icon={<GitCommit className="w-5 h-5" />}
            />
            <KpiCard
              title="Avg Maintainability"
              value={`${result.complexity.summary.avg_mi_score}/100`}
              subtitle="Radon MI Score"
              badge={{
                text: result.complexity.summary.avg_mi_score >= 65 ? 'Maintainable' : 'Low MI',
                variant: result.complexity.summary.avg_mi_score >= 65 ? 'positive' : 'warning',
              }}
              icon={<Activity className="w-5 h-5" />}
            />
            <KpiCard
              title="Circular Deps"
              value={result.graph.stats.cycle_count}
              subtitle="AST Cyclic Imports"
              badge={{
                text: result.graph.stats.cycle_count > 0 ? 'Loops Found' : 'Clean (0)',
                variant: result.graph.stats.cycle_count > 0 ? 'critical' : 'positive',
              }}
              icon={<Network className="w-5 h-5" />}
            />
          </div>

          {/* Tab Navigation */}
          <div className="border-b border-slate-200 dark:border-slate-800">
            <nav className="flex items-center gap-2 overflow-x-auto pb-px">
              {[
                { id: 'hotspots', label: '🎯 Hotspots', count: result.hotspots.hotspots.length },
                { id: 'complexity', label: '📊 Complexity', count: result.complexity.summary.total_functions },
                { id: 'graph', label: '🔀 Dependency Graph', count: result.graph.stats.node_count },
                { id: 'churn', label: '📈 Git Churn', count: result.churn.most_churned.length },
                { id: 'report', label: '🤖 AI Report', count: null },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`flex items-center gap-2 px-4 py-3 text-sm font-bold border-b-2 whitespace-nowrap transition-colors ${
                    activeTab === tab.id
                      ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                      : 'border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
                  }`}
                >
                  <span>{tab.label}</span>
                  {tab.count !== null && (
                    <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                      {tab.count}
                    </span>
                  )}
                </button>
              ))}
            </nav>
          </div>

          {/* Active Tab Content */}
          <div className="pt-2">
            {activeTab === 'hotspots' && <HotspotsTab data={result.hotspots} />}
            {activeTab === 'complexity' && <ComplexityTab data={result.complexity} />}
            {activeTab === 'graph' && <DependencyGraphTab data={result.graph} />}
            {activeTab === 'churn' && <ChurnTab data={result.churn} />}
            {activeTab === 'report' && (
              <AiReportTab
                analysisId={analysis.id}
                repoName={analysis.repo_name}
                reportText={analysis.report_text}
                reportStatus={analysis.report_status}
                onReportUpdated={() => refetch()}
              />
            )}
          </div>
        </>
      )}
    </div>
  );
};
