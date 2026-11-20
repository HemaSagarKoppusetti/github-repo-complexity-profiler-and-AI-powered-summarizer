import React from 'react';

interface StatusBadgeProps {
  status: string;
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = 'md' }) => {
  const norm = status.toLowerCase();

  let bgClass = 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300';
  let label = status;

  if (norm.includes('completed') || norm.includes('low') || norm.includes('ok')) {
    bgClass = 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800';
  } else if (norm.includes('running') || norm.includes('medium')) {
    bgClass = 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800';
  } else if (norm.includes('critical') || norm.includes('failed') || norm.includes('error')) {
    bgClass = 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-400 dark:border-rose-800';
  } else if (norm.includes('high')) {
    bgClass = 'bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-950/40 dark:text-orange-400 dark:border-orange-800';
  } else if (norm.includes('queued')) {
    bgClass = 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-400 dark:border-blue-800';
  }

  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs md:text-sm';

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-medium rounded-full border ${sizeClasses} ${bgClass}`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current opacity-75"></span>
      {label}
    </span>
  );
};
