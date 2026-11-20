import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Copy,
  Check,
  RefreshCw,
  Download,
  FileText,
  FileCode,
  FileSpreadsheet,
  AlertTriangle,
} from 'lucide-react';
import { api } from '../../api/client';

interface AiReportTabProps {
  analysisId: string;
  repoName: string;
  reportText: string | null;
  reportStatus: string;
  onReportUpdated?: (newText: string) => void;
}

export const AiReportTab: React.FC<AiReportTabProps> = ({
  analysisId,
  repoName,
  reportText,
  reportStatus,
  onReportUpdated,
}) => {
  const [copied, setCopied] = useState<boolean>(false);
  const [regenerating, setRegenerating] = useState<boolean>(false);
  const [regenError, setRegenError] = useState<string | null>(null);

  const handleCopy = () => {
    if (!reportText) return;
    navigator.clipboard.writeText(reportText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleRegenerate = async () => {
    setRegenerating(true);
    setRegenError(null);
    try {
      const res = await api.rerunReport(analysisId);
      if (onReportUpdated) {
        onReportUpdated(res.report_text);
      }
    } catch (err: any) {
      setRegenError(err.message || 'Failed to regenerate report');
    } finally {
      setRegenerating(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Action Header Banner */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
        <div>
          <h3 className="text-base font-bold text-slate-900 dark:text-white">
            Architectural & Risk Assessment Report
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Synthesized by OpenRouter LLM based strictly on static metrics and churn profile.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {reportText && (
            <button
              onClick={handleCopy}
              className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? 'Copied' : 'Copy Text'}
            </button>
          )}

          <button
            onClick={handleRegenerate}
            disabled={regenerating}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-xl bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${regenerating ? 'animate-spin' : ''}`} />
            {regenerating ? 'Regenerating...' : 'Regenerate Report'}
          </button>
        </div>
      </div>

      {/* Failure Banner */}
      {reportStatus === 'failed' && (
        <div className="p-4 rounded-xl border border-amber-300 dark:border-amber-900 bg-amber-50 dark:bg-amber-950/40 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
          <div>
            <h4 className="text-xs font-bold text-amber-900 dark:text-amber-300">
              AI Generation Status Warning
            </h4>
            <p className="text-xs text-amber-700 dark:text-amber-400 mt-0.5">
              The automated AI summariser encountered a rate limit or timeout. All quantitative metrics are preserved above. You can retry with the "Regenerate Report" button.
            </p>
          </div>
        </div>
      )}

      {regenError && (
        <div className="p-3 text-xs rounded-xl bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-400 border border-rose-200 dark:border-rose-900">
          {regenError}
        </div>
      )}

      {/* Rendered Markdown Body */}
      <div className="p-6 sm:p-8 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
        {reportText ? (
          <article className="prose dark:prose-invert prose-slate max-w-none text-sm leading-relaxed prose-headings:font-bold prose-h2:text-base prose-h2:mt-6 prose-h2:mb-3 prose-p:my-2 prose-ul:my-2 prose-li:my-0.5 prose-code:font-mono prose-code:text-xs prose-code:bg-slate-100 dark:prose-code:bg-slate-800 prose-code:px-1 prose-code:py-0.5 prose-code:rounded">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {reportText}
            </ReactMarkdown>
          </article>
        ) : (
          <div className="py-12 text-center text-slate-400">
            <p>No report text available.</p>
          </div>
        )}
      </div>

      {/* Export Section */}
      <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3 flex items-center gap-1.5">
          <Download className="w-4 h-4 text-blue-500" />
          Export Artifacts
        </h4>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <a
            href={api.getReportMdUrl(analysisId)}
            download={`${repoName}_report.md`}
            className="flex items-center justify-center gap-2 p-3 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800 text-xs font-medium text-slate-800 dark:text-slate-200 transition-colors"
          >
            <FileText className="w-4 h-4 text-blue-500" />
            Download Markdown (.md)
          </a>

          <a
            href={api.getReportPdfUrl(analysisId)}
            download={`${repoName}_report.pdf`}
            className="flex items-center justify-center gap-2 p-3 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800 text-xs font-medium text-slate-800 dark:text-slate-200 transition-colors"
          >
            <FileSpreadsheet className="w-4 h-4 text-rose-500" />
            Download PDF Report (.pdf)
          </a>

          <a
            href={api.getExportJsonUrl(analysisId)}
            download={`${repoName}_export.json`}
            className="flex items-center justify-center gap-2 p-3 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800 text-xs font-medium text-slate-800 dark:text-slate-200 transition-colors"
          >
            <FileCode className="w-4 h-4 text-emerald-500" />
            Export Raw JSON (.json)
          </a>
        </div>
      </div>
    </div>
  );
};
