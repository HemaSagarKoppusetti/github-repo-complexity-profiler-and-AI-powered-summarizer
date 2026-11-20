# backend/app/main.py
"""FastAPI application entry point."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.analyses import router as analyses_router
from app.api.health import router as health_router
from app.config import settings
from app.db.database import init_db

# Configure structured logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("profiler")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context for startup and shutdown."""
    logger.info("Initializing GitHub Repo Profiler API backend...")
    init_db()
    yield
    logger.info("Shutting down API backend...")


app = FastAPI(
    title="GitHub Repo Complexity Profiler API",
    description="Automated seven-stage static complexity, churn, and architecture analysis for GitHub repositories.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Simple In-Memory Per-IP Rate Limiter ──────────────────────────────────────
_request_counts: dict[str, list[float]] = {}


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next) -> Response:
    """Enforces a basic per-IP sliding window rate limit."""
    # Skip rate limiting for static docs and health endpoints
    if request.url.path in {"/docs", "/redoc", "/openapi.json", "/api/health"}:
        return await call_next(request)

    client_ip = request.client.host if request.client else "127.0.0.1"
    now = time.time()
    window = 60.0  # 1 minute window

    # Clean older timestamps
    history = _request_counts.get(client_ip, [])
    history = [t for t in history if now - t < window]

    if len(history) >= settings.RATE_LIMIT_PER_MINUTE:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": f"Too many requests. Limit is {settings.RATE_LIMIT_PER_MINUTE} requests per minute.",
                }
            },
        )

    history.append(now)
    _request_counts[client_ip] = history
    return await call_next(request)


# ── Consistent Error Response Handlers ─────────────────────────────────────────
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        return JSONResponse(status_code=exc.status_code, content={"error": detail})

    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        422: "UNPROCESSABLE_ENTITY",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_SERVER_ERROR",
    }
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code_map.get(exc.status_code, "ERROR"),
                "message": str(detail),
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Build clean human-readable error messages from Pydantic errors
    messages = []
    for err in exc.errors():
        field = " -> ".join(str(loc) for loc in err.get("loc", []))
        msg = err.get("msg", "Invalid value")
        messages.append(f"{field}: {msg}" if field else msg)

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "; ".join(messages),
            }
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled server exception: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred processing your request.",
            }
        },
    )


# ── Register Routers ──────────────────────────────────────────────────────────
app.include_router(health_router, prefix="/api")
app.include_router(analyses_router, prefix="/api")
