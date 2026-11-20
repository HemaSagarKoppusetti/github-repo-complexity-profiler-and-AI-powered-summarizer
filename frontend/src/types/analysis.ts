export type AnalysisStatus = 'queued' | 'running' | 'completed' | 'failed';
export type ReportStatus = 'pending' | 'completed' | 'failed' | 'skipped';

export interface KeyMetrics {
  total_files: number;
  total_loc: number;
  total_commits: number;
  total_authors: number;
  repo_age_days: number;
  avg_mi_score: number;
  circular_deps: number;
  critical_hotspots: number;
  high_hotspots: number;
}

export interface AnalysisSummary {
  id: string;
  github_url: string;
  repo_name: string;
  status: AnalysisStatus;
  stage: string | null;
  percent: number;
  error: string | null;
  report_status: ReportStatus;
  created_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
  key_metrics: KeyMetrics | null;
}

export interface HotspotItem {
  rel_path: string;
  commit_count: number;
  churn_rate: number;
  author_count: number;
  last_changed: string | null;
  mi_score: number;
  mi_rank: string;
  avg_cc: number;
  max_cc: number;
  hotspot_fn: string | null;
  risk_score: number;
  risk_tier: string;
}

export interface HotspotsData {
  hotspots: HotspotItem[];
  top_hotspots: HotspotItem[];
  summary: {
    total_files_scored: number;
    critical_count: number;
    high_count: number;
    medium_count: number;
    low_count: number;
    top_hotspot: string | null;
    top_hotspot_fn: string | null;
    critical_files: string[];
  };
}

export interface FunctionComplexity {
  name: string;
  type: string;
  complexity: number;
  rank: string;
  lineno: number;
  filepath?: string;
}

export interface ComplexityFileResult {
  filepath: string;
  mi_score: number;
  mi_rank: string;
  functions: FunctionComplexity[];
  avg_cc: number;
  max_cc: number;
  hotspot_fn: string | null;
  error: string | null;
}

export interface ComplexityData {
  results: ComplexityFileResult[];
  summary: {
    total_files_analysed: number;
    total_functions: number;
    avg_mi_score: number;
    low_mi_file_count: number;
    rank_distribution: Record<string, number>;
    top_complex_functions: FunctionComplexity[];
    least_maintainable: ComplexityFileResult[];
  };
}

export interface ChurnStats {
  total_commits: number;
  total_authors: number;
  repo_age_days: number;
  first_commit: string;
  last_commit: string;
}

export interface FileChurnData {
  rel_path: string;
  commit_count: number;
  authors: string[];
  author_count: number;
  first_changed: string | null;
  last_changed: string | null;
  age_days: number;
  churn_rate: number;
}

export interface ChurnData {
  file_churn: Record<string, FileChurnData>;
  most_churned: FileChurnData[];
  stats: ChurnStats;
}

export interface GraphNode {
  id: string;
  label: string;
  full_name: string;
  in_degree: number;
  out_degree: number;
  in_cycle: boolean;
}

export interface GraphEdge {
  source: string;
  target: string;
}

export interface GraphStats {
  node_count: number;
  edge_count: number;
  density: number;
  cycle_count: number;
  has_cycles: boolean;
  external_deps: number;
}

export interface HubModule {
  module: string;
  imported_by: number;
}

export interface GraphData {
  nodes: string[];
  edges: [string, string][];
  cycles: string[][];
  hub_modules: HubModule[];
  isolated_modules: string[];
  external_packages: string[];
  stats: GraphStats;
  graph_elements?: {
    nodes: GraphNode[];
    edges: GraphEdge[];
  };
}

export interface ManifestFile {
  path: string;
  rel_path: string;
  filename: string;
  extension: string;
  language: string;
  loc: number;
  can_profile: boolean;
}

export interface ManifestData {
  files: ManifestFile[];
  total_files: number;
  total_loc: number;
  language_breakdown: Record<string, number>;
  python_files: string[];
  total_python_files: number;
  truncated?: boolean;
  warning?: string | null;
}

export interface FullAnalysisResult {
  repo_name: string;
  github_url: string;
  manifest: ManifestData;
  complexity: ComplexityData;
  graph: GraphData;
  churn: ChurnData;
  hotspots: HotspotsData;
  duration_seconds: number;
}

export interface AnalysisDetail {
  id: string;
  github_url: string;
  repo_name: string;
  status: AnalysisStatus;
  stage: string | null;
  percent: number;
  error: string | null;
  report_status: ReportStatus;
  report_text: string | null;
  created_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
  result: FullAnalysisResult | null;
}

export interface AnalysisEvent {
  analysis_id: string;
  stage: string;
  percent: number;
  message: string;
  status: string;
  timestamp: string;
  error?: string | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface HealthInfo {
  status: string;
  version: string;
  environment: string;
  llm: {
    provider: string;
    model: string;
    configured: boolean;
  };
}
