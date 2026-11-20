import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Activity,
  History as HistoryIcon,
  GitCompare,
  Sun,
  Moon,
  Github,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import { api } from '../api/client';
import { HealthInfo } from '../types/analysis';

export const Navbar: React.FC = () => {
  const location = useLocation();
  const [darkMode, setDarkMode] = useState<boolean>(() => {
    return (
      localStorage.getItem('theme') === 'dark' ||
      (!('theme' in localStorage) &&
        window.matchMedia('(prefers-color-scheme: dark)').matches)
    );
  });
  const [health, setHealth] = useState<HealthInfo | null>(null);

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  }, [darkMode]);

  useEffect(() => {
    api.getHealth()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  const navLinks = [
    { to: '/', label: 'Analyse', icon: <Activity className="w-4 h-4" /> },
    { to: '/history', label: 'History', icon: <HistoryIcon className="w-4 h-4" /> },
    { to: '/compare', label: 'Compare', icon: <GitCompare className="w-4 h-4" /> },
  ];

  return (
    <header className="sticky top-0 z-50 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b border-slate-200 dark:border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand */}
        <Link to="/" className="flex items-center gap-2.5 group">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center text-white shadow-sm shadow-blue-500/20 group-hover:scale-105 transition-transform">
            <span className="text-xl">🔍</span>
          </div>
          <div>
            <h1 className="text-base font-bold text-slate-900 dark:text-white leading-tight flex items-center gap-1.5">
              Repo Complexity Profiler
              <span className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-400">
                v2.0
              </span>
            </h1>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              Static Complexity, Churn & Architecture AI
            </p>
          </div>
        </Link>

        {/* Center Nav */}
        <nav className="flex items-center gap-1">
          {navLinks.map((item) => {
            const isActive = location.pathname === item.to;
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-700 dark:bg-blue-950/60 dark:text-blue-400'
                    : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
                }`}
              >
                {item.icon}
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* Right Tools */}
        <div className="flex items-center gap-3">
          {/* Health Pill */}
          <div
            className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50"
            title={health ? `API Online | LLM: ${health.llm.model} (${health.llm.configured ? 'Configured' : 'Missing Key'})` : 'API Disconnected'}
          >
            {health ? (
              <>
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                <span className="text-slate-600 dark:text-slate-300 font-medium">API Ready</span>
              </>
            ) : (
              <>
                <XCircle className="w-3.5 h-3.5 text-rose-500" />
                <span className="text-slate-600 dark:text-slate-300 font-medium">API Offline</span>
              </>
            )}
          </div>

          {/* Theme Toggle */}
          <button
            onClick={() => setDarkMode(!darkMode)}
            className="p-2 rounded-lg text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            title={darkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
            aria-label="Toggle theme"
          >
            {darkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>

          {/* GitHub Source */}
          <a
            href="https://github.com/pallets/markupsafe"
            target="_blank"
            rel="noopener noreferrer"
            className="p-2 rounded-lg text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            title="Sample GitHub Repository"
          >
            <Github className="w-4 h-4" />
          </a>
        </div>
      </div>
    </header>
  );
};
