# 🚀 GitHub Repo Complexity Profiler

A production-quality full-stack web application that autonomously clones, profiles, and visualizes the architectural complexity, maintainability, and hotspot risks of any public Python repository on GitHub.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![React](https://img.shields.io/badge/react-18.3-cyan)
![TypeScript](https://img.shields.io/badge/typescript-5.5-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-teal)
![Docker](https://img.shields.io/badge/docker-ready-2496ED)

---

## ✨ Features

- **7-Stage Analysis Pipeline:**
  1. **Shallow Clone:** Windows-safe Git clone with size limits (<300MB) and directory cleanup.
  2. **File Scanner:** LOC counting and language composition detection across repository files.
  3. **Radon Complexity & Maintainability:** Cyclomatic Complexity (CC) rank distribution (A-F) and Maintainability Index (MI).
  4. **AST Dependency Graph:** Abstract Syntax Tree module resolution, circular dependency detection (Johnson's algorithm), and hub module identification.
  5. **Single-Pass Git Churn:** High-performance single-pass streaming parser calculating commit frequency, author counts, and repository age.
  6. **Hotspot Risk Engine:** Multi-factor risk scoring identifying files with high churn and low maintainability.
  7. **AI Executive Summary:** Automated architectural critique, top risk highlights, and refactoring recommendations powered by OpenRouter LLMs.
- **Modern Interactive Dashboard:**
  - **Live Progress Stepper:** Real-time Server-Sent Events (SSE) streaming stage percentage and diagnostic messages.
  - **KPI Cards:** Total files, LOC, commits, maintainability score, and circular dependency counts.
  - **Hotspots Table:** Sortable, filterable table with color-coded risk tiers (🔴 Critical, 🟠 High, 🟡 Medium, 🟢 Low) and an inspectable function drawer.
  - **Complexity Charts:** Recharts bar distributions of CC ranks and top complex functions.
  - **Interactive Dependency Canvas:** Native Cytoscape.js directed graph with node sizing by in-degree, red cycle highlighting, neighbor illumination, and module search.
  - **History & Comparison:** Searchable past analyses table and side-by-side KPI comparison tool.
  - **Multi-Format Exports:** Download reports as formatted Markdown, executive PDF documents, or raw JSON.

---

## 🛠️ Technology Stack

| Layer | Technologies |
|---|---|
| **Backend** | Python 3.11+, FastAPI, Pydantic v2, SQLModel / SQLAlchemy, SQLite (`data/profiler.db`), Radon, NetworkX, GitPython, fpdf2, Ruff |
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query v5, React Router v6, Cytoscape.js + Dagre, Recharts, Lucide Icons, Vitest |
| **Containers** | Docker, Docker Compose, Multi-stage builds |

---

## 📋 Prerequisites

- **Python:** 3.11 or higher
- **Node.js:** 20 or higher (npm 9+)
- **Git:** Installed and available on system PATH
- **(Optional) Docker Desktop:** For running via containerization

---

## ⚡ Quick Start (Windows 11 Local Development)

We provide an automated, one-command PowerShell startup script that creates the Python virtual environment, installs dependencies, builds the database, and launches both services simultaneously:

```powershell
# In PowerShell:
.\scripts\dev.ps1
```

Once started:
- **Frontend:** http://localhost:5173
- **FastAPI API & OpenAPI Docs:** http://localhost:8000/docs
- **SQLite Database:** `backend/data/profiler.db`

---

## 🐳 Quick Start with Docker Compose

To run the entire full-stack application in isolated production containers:

```bash
# 1. Copy environment variables
cp .env.example .env

# 2. Build and run containers
docker-compose up --build
```

- **Frontend & App:** http://localhost:3000
- **Backend API Docs:** http://localhost:8000/docs

---

## 🔑 Environment Configuration

Create a `.env` file in the root directory (or copy from `.env.example`):

```env
# Server Configuration
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# LLM Provider Configuration (OpenRouter)
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=openrouter/free

# Analysis Guardrails & Limits
MAX_REPO_SIZE_MB=300
CLONE_TIMEOUT_SECONDS=180
MAX_PYTHON_FILES_ANALYSED=2000
MAX_CONCURRENT_JOBS=2
RATE_LIMIT_PER_MINUTE=30
```

### Obtaining a Free OpenRouter API Key
1. Go to [OpenRouter.ai](https://openrouter.ai/) and sign in.
2. Navigate to **Keys** and click **Create Key**.
3. Paste the key into `.env` as `OPENROUTER_API_KEY`.
4. The default model `openrouter/free` automatically routes to available zero-cost models (such as Cohere, DeepSeek R1, or Llama).

*Note: If no API key is provided, the application will still profile the entire repository and produce complete metrics, but the final report stage will display a clear "API key not configured" status without crashing.*

---

## 🧪 Testing & Verification

### Run Backend Tests (pytest)
```bash
.\venv\Scripts\pytest -v
```
*(All 13 test suites verify URL validation, risk score mathematics, LLM retry and reasoning fallbacks, and all API endpoints).*

### Run Frontend Tests (vitest)
```bash
cd frontend
npx vitest run
```

### Run Full End-to-End Smoke Test
Run the automated smoke test script to verify cloning, profiling, risk calculation, and hotspot identification on `pallets/markupsafe`:

```powershell
.\venv\Scripts\python scripts/smoke_test.py
```
*Asserts that `src/markupsafe/__init__.py` is ranked as a Critical or High risk hotspot.*

---

## 🔧 Troubleshooting & Known Nuances

### 1. Windows File Permissions & Read-Only `.git`
- **Issue:** On Windows, Git marks objects in `.git` as read-only, which causes standard `shutil.rmtree` calls to fail with `PermissionError`.
- **Solution:** Our cloner service (`backend/app/core/cloner.py`) includes a custom `on_exc` callback that clears `stat.S_IWRITE` before retrying, plus a multi-phase fallback loop.

### 2. GitPython `kill_after_timeout` on Windows
- **Issue:** GitPython raises `"kill_after_timeout feature is not supported on Windows"`.
- **Solution:** Timeout flags are conditionally guarded so Windows systems execute safe subprocess execution without exceptions.

### 3. OpenRouter Free Model Reasoning Tokens
- **Issue:** Several free models on OpenRouter (e.g. Cohere or DeepSeek R1) output reasoning tokens into an internal reasoning field rather than `content`, occasionally exhausting low token limits.
- **Solution:** The `OpenRouterLLMClient` allocates 3,000 max tokens and implements automated fallback to `msg.get("reasoning")` if `content` is empty.

---

## 📚 Documentation Links

- [System Architecture & Data Flow](docs/ARCHITECTURE.md)
- [API Specification & Schemas](docs/API.md)
- [Architectural Decisions & Trade-Offs](docs/DECISIONS.md)
