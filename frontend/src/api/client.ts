import {
  AnalysisDetail,
  AnalysisEvent,
  AnalysisSummary,
  HealthInfo,
  PaginatedResponse,
} from '../types/analysis';

const BASE_URL = '/api';

class ApiError extends Error {
  code: string;
  constructor(message: string, code: string = 'API_ERROR') {
    super(message);
    this.name = 'ApiError';
    this.code = code;
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  const response = await fetch(url, { ...options, headers });

  if (!response.ok) {
    let errorDetail = { code: 'HTTP_' + response.status, message: response.statusText };
    try {
      const data = await response.json();
      if (data.error) {
        errorDetail = data.error;
      }
    } catch {
      // not JSON
    }
    throw new ApiError(errorDetail.message, errorDetail.code);
  }

  return response.json();
}

export const api = {
  async getHealth(): Promise<HealthInfo> {
    return request<HealthInfo>('/health');
  },

  async createAnalysis(
    github_url: string,
    top_n: number = 10,
    force: boolean = false
  ): Promise<{ id: string; status: string; repo_name: string; cached: boolean }> {
    return request('/analyses', {
      method: 'POST',
      body: JSON.stringify({ github_url, top_n, force }),
    });
  },

  async listAnalyses(
    page: number = 1,
    size: number = 20,
    search?: string,
    status?: string
  ): Promise<PaginatedResponse<AnalysisSummary>> {
    const params = new URLSearchParams({
      page: page.toString(),
      size: size.toString(),
    });
    if (search) params.append('search', search);
    if (status) params.append('status', status);

    return request<PaginatedResponse<AnalysisSummary>>(`/analyses?${params.toString()}`);
  },

  async getAnalysis(id: string): Promise<AnalysisDetail> {
    return request<AnalysisDetail>(`/analyses/${id}`);
  },

  async deleteAnalysis(id: string): Promise<{ success: boolean; message: string }> {
    return request(`/analyses/${id}`, { method: 'DELETE' });
  },

  async rerunReport(id: string): Promise<{ id: string; report_status: string; report_text: string }> {
    return request(`/analyses/${id}/rerun-report`, { method: 'POST' });
  },

  getReportMdUrl(id: string): string {
    return `${BASE_URL}/analyses/${id}/report.md`;
  },

  getReportPdfUrl(id: string): string {
    return `${BASE_URL}/analyses/${id}/report.pdf`;
  },

  getExportJsonUrl(id: string): string {
    return `${BASE_URL}/analyses/${id}/export.json`;
  },

  subscribeToEvents(
    id: string,
    onMessage: (event: AnalysisEvent) => void,
    onError?: (error: Event) => void
  ): () => void {
    const sse = new EventSource(`${BASE_URL}/analyses/${id}/events`);

    sse.onmessage = (e) => {
      try {
        const data: AnalysisEvent = JSON.parse(e.data);
        onMessage(data);
        if (data.status === 'completed' || data.status === 'failed') {
          sse.close();
        }
      } catch (err) {
        console.error('Failed to parse SSE event data', err);
      }
    };

    sse.onerror = (e) => {
      if (onError) onError(e);
      // Wait or auto-reconnect handled by EventSource
    };

    return () => {
      sse.close();
    };
  },
};
