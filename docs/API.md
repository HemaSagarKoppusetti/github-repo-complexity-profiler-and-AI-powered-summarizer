# GitHub Repo Complexity Profiler — API Specification

The API is built with FastAPI, enforces Pydantic v2 validation, and exposes interactive OpenAPI documentation at `/docs` and `/redoc`.

- **Base URL:** `http://localhost:8000` (or `http://localhost:3000/api` when routed through Docker/Vite proxy)
- **Content-Type:** `application/json` (unless downloading `.md` or `.pdf`)

---

## Error Handling Convention

All error responses adhere to the standard error structure:

```json
{
  "error": {
    "code": "ERROR_CODE_STRING",
    "message": "Human-readable description of what went wrong."
  }
}
```

Common status codes:
- `400 Bad Request`: Invalid state, non-existent report download, or cache constraints.
- `404 Not Found`: Analysis record not found.
- `422 Unprocessable Content`: Failed payload validation (e.g. invalid GitHub URL pattern).
- `429 Too Many Requests`: Rate limit exceeded for client IP.
- `500 Internal Server Error`: Unhandled system error.

---

## Endpoints Overview

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/health` | Service health and LLM provider status |
| `POST` | `/api/analyses` | Submit a repository for complexity profiling |
| `GET` | `/api/analyses` | List past analyses (paginated, searchable, filterable) |
| `GET` | `/api/analyses/{id}` | Retrieve complete analysis metrics and report |
| `GET` | `/api/analyses/{id}/events` | Real-time Server-Sent Events (SSE) stream |
| `POST` | `/api/analyses/{id}/rerun-report` | Re-generate only the AI summary report |
| `GET` | `/api/analyses/{id}/report.md` | Download Markdown report |
| `GET` | `/api/analyses/{id}/report.pdf` | Download formatted PDF report |
| `GET` | `/api/analyses/{id}/export.json` | Download raw JSON analysis data |
| `DELETE` | `/api/analyses/{id}` | Delete analysis record |

---

## Endpoint Details

### 1. Health Check
`GET /api/health`

**Response:**
```json
{
  "status": "ok",
  "app_name": "GitHub Repo Complexity Profiler",
  "version": "1.0.0",
  "llm_provider": "openrouter",
  "llm_model": "openrouter/free",
  "llm_configured": true
}
```

---

### 2. Create Analysis Job
`POST /api/analyses`

Submits a repository URL for asynchronous profiling. If analysed within the last 24 hours, the cached result is returned unless `force=true`.

**Request Body:**
```json
{
  "github_url": "https://github.com/pallets/markupsafe",
  "top_n": 10,
  "force": false
}
```

**Response (`201 Created` or `200 OK` if cached):**
```json
{
  "id": "e0a7f160-b883-43c2-8404-58674d82522b",
  "status": "queued",
  "message": "Analysis queued for background processing."
}
```

---

### 3. List Analyses History
`GET /api/analyses`

Returns a paginated list of past analyses with summary metrics.

**Query Parameters:**
- `page` *(int, default: 1)*: Page number (1-based).
- `page_size` *(int, default: 10, max: 100)*: Items per page.
- `search` *(string, optional)*: Case-insensitive search on repo name or GitHub URL.
- `status` *(string, optional)*: Filter by `queued`, `running`, `completed`, or `failed`.

**Response:**
```json
{
  "items": [
    {
      "id": "e0a7f160-b883-43c2-8404-58674d82522b",
      "github_url": "https://github.com/pallets/markupsafe",
      "repo_name": "markupsafe",
      "status": "completed",
      "stage": "complete",
      "percent": 100,
      "report_status": "completed",
      "created_at": "2026-11-19T09:12:00Z",
      "completed_at": "2026-11-19T09:12:58Z",
      "duration_seconds": 58,
      "metrics": {
        "total_files": 24,
        "total_loc": 2850,
        "total_commits": 142,
        "avg_mi_score": 78.4,
        "circular_deps_count": 0,
        "critical_hotspots_count": 1
      }
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 10,
  "total_pages": 1
}
```

---

### 4. Get Analysis Details
`GET /api/analyses/{id}`

Returns the full analysis state including all metrics from the 7-stage pipeline.

**Response:**
```json
{
  "id": "e0a7f160-b883-43c2-8404-58674d82522b",
  "github_url": "https://github.com/pallets/markupsafe",
  "repo_name": "markupsafe",
  "status": "completed",
  "stage": "complete",
  "percent": 100,
  "error": null,
  "report_text": "## 1. What This Codebase Does\n...",
  "report_status": "completed",
  "created_at": "2026-11-19T09:12:00Z",
  "completed_at": "2026-11-19T09:12:58Z",
  "duration_seconds": 58,
  "result": {
    "manifest": {
      "total_files": 24,
      "total_loc": 2850,
      "language_breakdown": {"Python": 14, "C": 2, "Markdown": 4},
      "python_files": ["src/markupsafe/__init__.py", "..."]
    },
    "complexity": {
      "results": [...],
      "summary": {
        "total_files_analysed": 14,
        "total_functions": 45,
        "avg_mi_score": 78.4,
        "cc_distribution": {"A": 38, "B": 5, "C": 2, "D": 0, "E": 0, "F": 0},
        "top_complex_functions": [...]
      }
    },
    "graph": {
      "nodes": [{"id": "markupsafe", "in_degree": 3, "out_degree": 2, "in_cycle": false}],
      "edges": [{"source": "_speedups", "target": "markupsafe"}],
      "cycles": [],
      "stats": {"node_count": 5, "edge_count": 6, "cycle_count": 0}
    },
    "churn": {
      "stats": {"total_commits": 142, "unique_authors": 18, "repo_age_days": 4200},
      "most_churned": [{"path": "src/markupsafe/__init__.py", "commits": 73, "authors": 12, "last_changed": "2024-02-15"}]
    },
    "hotspots": {
      "hotspots": [
        {
          "rel_path": "src/markupsafe/__init__.py",
          "risk_score": 0.8552,
          "risk_tier": "Critical",
          "churn_commits": 73,
          "complexity_max_cc": 6,
          "complexity_mi": 50.95,
          "most_complex_func": "escape (CC 6)"
        }
      ],
      "summary": {"critical_count": 1, "high_count": 0, "medium_count": 2, "low_count": 11}
    }
  }
}
```

---

### 5. Server-Sent Events (SSE) Stream
`GET /api/analyses/{id}/events`

Streams real-time analysis progress directly to the browser.

**Event Format (`text/event-stream`):**
```text
data: {"stage": "clone", "percent": 15, "message": "Cloning repository...", "status": "running"}

data: {"stage": "complexity", "percent": 35, "message": "Profiling cyclomatic complexity and maintainability index...", "status": "running"}

data: {"stage": "complete", "percent": 100, "message": "Analysis finished successfully.", "status": "completed"}
```

---

### 6. Rerun AI Report
`POST /api/analyses/{id}/rerun-report`

Re-triggers LLM summary generation using cached metrics in the database without recloning the repository.

**Response:**
```json
{
  "id": "e0a7f160-b883-43c2-8404-58674d82522b",
  "status": "completed",
  "report_status": "completed",
  "report_text": "## 1. What This Codebase Does\n..."
}
```

---

### 7. File Exports
- `GET /api/analyses/{id}/report.md`
  - Returns `text/markdown; charset=utf-8` with `Content-Disposition: attachment; filename="{repo_name}_report.md"`.
- `GET /api/analyses/{id}/report.pdf`
  - Returns `application/pdf` with `Content-Disposition: attachment; filename="{repo_name}_report.pdf"`.
- `GET /api/analyses/{id}/export.json`
  - Returns `application/json` with `Content-Disposition: attachment; filename="{repo_name}_analysis.json"`.

---

### 8. Delete Analysis
`DELETE /api/analyses/{id}`

Deletes the record from SQLite.

**Response:**
```json
{
  "id": "e0a7f160-b883-43c2-8404-58674d82522b",
  "deleted": true
}
```
