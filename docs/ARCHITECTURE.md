# System Architecture & Data Flow

This document details the architectural layout, data pipeline stages, and end-to-end communication pathways of the **GitHub Repo Complexity Profiler**.

---

## 1. High-Level Architecture Overview

```mermaid
graph TD
    Browser["React 18 + Vite Frontend\n(Tailwind CSS, TanStack Query, Cytoscape.js)"]
    API["FastAPI Web API (:8000)\n(/api/analyses, /events, /health)"]
    DB[("SQLite Database\n(data/profiler.db)")]
    Worker["Background Worker\n(asyncio Semaphore limit=2)"]
    Pipeline["7-Stage Pipeline Service\n(Cloner -> Scanner -> Radon -> AST -> Churn -> Hotspots -> LLM)"]
    GitRemote["Remote GitHub Repository"]
    OpenRouter["OpenRouter API\n(Free LLM: openrouter/free)"]

    Browser -->|"HTTP POST /api/analyses"| API
    Browser -->|"GET SSE /api/analyses/{id}/events"| API
    Browser -->|"GET /api/analyses/{id} / PDF / MD / JSON"| API
    API -->|"Job Record (Queued)"| DB
    API -->|"Enqueue background task"| Worker
    Worker -->|"Execute sequentially"| Pipeline
    Pipeline -->|"Clone via GitPython (shallow depth=1)"| GitRemote
    Pipeline -->|"Real-time stage events"| API
    Pipeline -->|"Generate architectural summary"| OpenRouter
    Pipeline -->|"Persist final metrics & report JSON"| DB
```

---

## 2. 7-Stage Analysis Pipeline & Progress Weights

Each stage computes domain-specific metrics and emits progress over Server-Sent Events (SSE). Cloned repositories are strictly cleaned up in a `finally` block with Windows-safe permissions.

```mermaid
flowchart LR
    S1["1. Clone (15%)\nShallow git clone\nSize check (<300MB)"] --> S2["2. Scan (5%)\nLOC & Language\nBreakdown (max 2000 py)"]
    S2 --> S3["3. Complexity (15%)\nRadon CC & MI\nRank distribution"]
    S3 --> S4["4. Graph (15%)\nAST Dependency Graph\nCycle detection (Johnson)"]
    S4 --> S5["5. Churn (20%)\nSingle-pass git log\nCommits & Authors"]
    S5 --> S6["6. Hotspots (5%)\nWeighted risk formula\nCritical / High / Med / Low"]
    S6 --> S7["7. AI Report (25%)\nOpenRouter prompt\nRetry with backoff"]
```

### Stage Weights & Output Summary

| Stage | Weight | Cumulative % | Core Operation | Fault Tolerance Policy |
|---|---|---|---|---|
| **1. Clone** | 15% | 15% | `git clone --depth 1` into temp dir; check repo size. | Fails job if repo is private, invalid, or > 300MB. |
| **2. Scan** | 5% | 20% | Recursive directory walk; count LOC; detect Python files. | Caps files at 2000; returns empty Python notice if 0 py files. |
| **3. Complexity** | 15% | 35% | Radon Cyclomatic Complexity (CC) and Maintainability Index (MI). | Per-file try/except prevents single syntax error from failing job. |
| **4. Graph** | 15% | 50% | AST import parsing, module nodes, edge dependencies, circular cycles. | Ignores syntax errors; returns empty graph if no imports found. |
| **5. Churn** | 20% | 70% | Single-pass `git log --name-only` streaming parser. | Falls back to empty churn if git log fails or repo has 1 commit. |
| **6. Hotspots** | 5% | 75% | Risk score formula: `0.5*churn + 0.3*CC + 0.2*(1-MI/100)`. | Guarded with divide-by-zero protection. |
| **7. AI Report** | 25% | 100% | Structured prompt sent to OpenRouter free LLM with exponential backoff. | If LLM fails after 2 retries, status is marked `report_status="failed"` without discarding metrics. |

---

## 3. Hotspot Risk Math

The risk score of any Python file $i$ is evaluated on normalized intervals $[0, 1]$:

$$\text{Risk}(i) = 0.50 \cdot \overline{\text{Churn}}(i) + 0.30 \cdot \overline{\text{CC}}(i) + 0.20 \cdot \overline{\text{InvMI}}(i)$$

Where:
- $\overline{\text{Churn}}(i) = \frac{\text{Commits}(i)}{\max(\text{Commits})}$
- $\overline{\text{CC}}(i) = \frac{\text{MaxCC}(i)}{\max(\text{MaxCC})}$
- $\overline{\text{InvMI}}(i) = \frac{100 - \text{MI}(i)}{100}$

### Risk Tiers
- **🔴 Critical:** $\text{Risk} \ge 0.70$
- **🟠 High:** $0.50 \le \text{Risk} < 0.70$
- **🟡 Medium:** $0.30 \le \text{Risk} < 0.50$
- **🟢 Low:** $\text{Risk} < 0.30$

---

## 4. Frontend Component & Page Architecture

```mermaid
graph TD
    App["App Root & Layout\n(React Router + TanStack Query)"]
    Navbar["Navbar\n(Brand, Health Indicator, Theme Toggle, Navigation)"]
    Home["Home Page\n(URL Input, Demo Chips, Slider, Recent List)"]
    Dashboard["Results Dashboard (/analyses/:id)\n(Header, KPI Cards, Export Actions)"]
    History["History Page\n(Searchable past table, Delete, Rerun)"]
    Compare["Compare Page\n(Side-by-side KPI & Hotspot Comparison)"]

    App --> Navbar
    App --> Home
    App --> Dashboard
    App --> History
    App --> Compare

    Dashboard --> Tab1["Hotspots Tab (Sortable Table + Drawer)"]
    Dashboard --> Tab2["Complexity Tab (CC Distribution Chart + Functions)"]
    Dashboard --> Tab3["Dependency Graph Tab (Cytoscape Canvas + Search + Cycles)"]
    Dashboard --> Tab4["Churn Tab (Most Churned Chart + Files Table)"]
    Dashboard --> Tab5["AI Report Tab (Markdown Viewer + Copy + Rerun)"]
```
