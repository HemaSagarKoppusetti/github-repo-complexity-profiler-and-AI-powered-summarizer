import React from 'react';

interface KpiCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  badge?: {
    text: string;
    variant: 'positive' | 'warning' | 'neutral' | 'critical';
  };
}

export const KpiCard: React.FC<KpiCardProps> = ({
  title,
  value,
  subtitle,
  icon,
  badge,
}) => {
  const badgeColors = {
    positive: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800',
    warning: 'bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-400 border-amber-200 dark:border-amber-800',
    critical: 'bg-rose-50 text-rose-700 dark:bg-rose-950/50 dark:text-rose-400 border-rose-200 dark:border-rose-800',
    neutral: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-slate-200 dark:border-slate-700',
  };

  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
            {title}
          </p>
          <h3 className="text-2xl font-bold text-slate-900 dark:text-white mt-1.5">
            {value}
          </h3>
        </div>
        <div className="p-2.5 bg-blue-50 dark:bg-blue-950/50 text-blue-600 dark:text-blue-400 rounded-lg">
          {icon}
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
        {subtitle && <span>{subtitle}</span>}
        {badge && (
          <span
            className={`ml-auto px-2 py-0.5 rounded-full border font-medium ${badgeColors[badge.variant]}`}
          >
            {badge.text}
          </span>
        )}
      </div>
    </div>
  );
};
