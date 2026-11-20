import React from 'react';
import {
  CheckCircle2,
  Circle,
  Loader2,
  AlertCircle,
  RotateCcw,
  GitBranch,
  FolderTree,
  Activity,
  Network,
  History,
  Flame,
  Bot,
} from 'lucide-react';

export interface ProgressStage {
  key: string;
  label: string;
  weight: number;
  icon: React.ReactNode;
}

export const STAGES: ProgressStage[] = [
  { key: 'clone', label: 'Clone Repository', weight: 15, icon: <GitBranch className="w-4 h-4" /> },
  { key: 'scan', label: 'Scan Codebase', weight: 20, icon: <FolderTree className="w-4 h-4" /> },
  { key: 'complexity', label: 'Complexity & MI (Radon)', weight: 35, icon: <Activity className="w-4 h-4" /> },
  { key: 'graph', label: 'Dependency Graph (AST)', weight: 50, icon: <Network className="w-4 h-4" /> },
  { key: 'churn', label: 'Git Churn Analysis', weight: 70, icon: <History className="w-4 h-4" /> },
  { key: 'hotspots', label: 'Hotspot Risk Ranking', weight: 75, icon: <Flame className="w-4 h-4" /> },
  { key: 'report', label: 'AI Architecture Report', weight: 100, icon: <Bot className="w-4 h-4" /> },
];

interface ProgressStepperProps {
  currentStage: string | null;
  percent: number;
  message?: string;
  status: string;
  error?: string | null;
  onRetry?: () => void;
}

export const ProgressStepper: React.FC<ProgressStepperProps> = ({
  currentStage,
  percent,
  message,
  status,
  error,
  onRetry,
}) => {
  const isFailed = status === 'failed';
  const isCompleted = status === 'completed';

  const getStageIndex = (stageKey: string) => {
    return STAGES.findIndex((s) => s.key === stageKey);
  };

  const activeIndex = currentStage ? getStageIndex(currentStage) : 0;

  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
            {!isCompleted && !isFailed && <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />}
            {isCompleted && <CheckCircle2 className="w-5 h-5 text-emerald-500" />}
            {isFailed && <AlertCircle className="w-5 h-5 text-rose-500" />}
            {isCompleted ? 'Analysis Complete' : isFailed ? 'Analysis Failed' : 'Analysing Repository...'}
          </h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            {message || 'Executing automated seven-stage profiling pipeline...'}
          </p>
        </div>
        <div className="text-right">
          <span className="text-2xl font-black text-blue-600 dark:text-blue-400">
            {percent}%
          </span>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="w-full bg-slate-100 dark:bg-slate-800 rounded-full h-2.5 overflow-hidden mb-6">
        <div
          className={`h-full transition-all duration-500 ease-out rounded-full ${
            isFailed
              ? 'bg-rose-500'
              : isCompleted
              ? 'bg-emerald-500'
              : 'bg-gradient-to-r from-blue-600 to-indigo-500 animate-pulse'
          }`}
          style={{ width: `${Math.min(100, Math.max(0, percent))}%` }}
        ></div>
      </div>

      {/* Stepper Stage Grid */}
      <div className="grid grid-cols-1 md:grid-cols-7 gap-2.5">
        {STAGES.map((stage, idx) => {
          let stageStatus: 'pending' | 'active' | 'completed' | 'failed' = 'pending';

          if (isCompleted || percent >= stage.weight) {
            stageStatus = 'completed';
          } else if (isFailed && idx === activeIndex) {
            stageStatus = 'failed';
          } else if (!isFailed && idx === activeIndex) {
            stageStatus = 'active';
          } else if (percent > (idx > 0 ? STAGES[idx - 1].weight : 0)) {
            stageStatus = 'active';
          }

          return (
            <div
              key={stage.key}
              className={`flex flex-col items-center text-center p-3 rounded-xl border transition-all ${
                stageStatus === 'active'
                  ? 'border-blue-500 bg-blue-50/50 dark:bg-blue-950/20 text-blue-700 dark:text-blue-300 shadow-sm'
                  : stageStatus === 'completed'
                  ? 'border-emerald-200 dark:border-emerald-900/50 bg-emerald-50/30 dark:bg-emerald-950/10 text-emerald-700 dark:text-emerald-400'
                  : stageStatus === 'failed'
                  ? 'border-rose-300 dark:border-rose-900 bg-rose-50/50 dark:bg-rose-950/20 text-rose-700 dark:text-rose-400'
                  : 'border-slate-200 dark:border-slate-800 opacity-50 text-slate-500 dark:text-slate-500'
              }`}
            >
              <div className="mb-2">
                {stageStatus === 'completed' && <CheckCircle2 className="w-5 h-5 text-emerald-500" />}
                {stageStatus === 'active' && <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />}
                {stageStatus === 'failed' && <AlertCircle className="w-5 h-5 text-rose-500" />}
                {stageStatus === 'pending' && <Circle className="w-5 h-5" />}
              </div>
              <span className="text-xs font-semibold leading-tight line-clamp-2">
                {stage.label}
              </span>
              <span className="text-[10px] mt-1 text-slate-400">
                Stage {idx + 1}
              </span>
            </div>
          );
        })}
      </div>

      {/* Error Callout & Retry */}
      {isFailed && (
        <div className="mt-6 p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-rose-600 dark:text-rose-400 shrink-0 mt-0.5" />
            <div>
              <h4 className="text-sm font-semibold text-rose-900 dark:text-rose-200">
                Pipeline Interrupted
              </h4>
              <p className="text-xs text-rose-700 dark:text-rose-300 mt-0.5">
                {error || 'An error occurred during repository analysis.'}
              </p>
            </div>
          </div>
          {onRetry && (
            <button
              onClick={onRetry}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-medium bg-rose-600 hover:bg-rose-700 text-white rounded-lg transition-colors shrink-0"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Retry Analysis
            </button>
          )}
        </div>
      )}
    </div>
  );
};
