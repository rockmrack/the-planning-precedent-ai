"""
Planning Precedent AI - FastAPI Application
Main entry point for the API server
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import structlog

from app.core.config import settings
from app.core.logging import setup_logging
from app.api.v1 import router as api_router

# Set up logging
setup_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan handler"""
    logger.info(
        "application_starting",
        app_name=settings.app_name,
        environment=settings.app_env,
    )
    yield
    logger.info("application_shutting_down")


# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="""
## Planning Precedent AI

A Retrieval-Augmented Generation (RAG) system for analysing UK planning decisions
and generating evidence-based planning arguments.

### Key Features

- **Semantic Search**: Find relevant planning precedents using natural language
- **AI Analysis**: Generate professional planning arguments with GPT-4o
- **Risk Assessment**: Understand the likelihood of approval
- **Export**: Generate PDF reports for applications and appeals

### Getting Started

1. Use `/api/v1/search` to find precedents for your development
2. Use `/api/v1/analyse` to generate detailed arguments
3. Use `/api/v1/export` to create professional reports

### Coverage

Currently focused on **London Borough of Camden** with emphasis on:
- Hampstead Town
- Belsize
- Frognal
- Swiss Cottage
- And other Camden wards

### UK Regulatory Compliance

All analysis references:
- Camden Local Plan 2017
- London Plan 2021
- National Planning Policy Framework (NPPF) 2023
- Town and Country Planning Act 1990
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
    )
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "An unexpected error occurred",
            "detail": str(exc) if settings.debug else None,
        },
    )


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests"""
    import time

    start_time = time.time()

    response = await call_next(request)

    duration_ms = (time.time() - start_time) * 1000

    logger.info(
        "http_request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round(duration_ms, 2),
    )

    return response


# Include API routes
app.include_router(api_router)


# Root endpoint
@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "description": "Planning Precedent AI - Find winning precedents for your development",
        "documentation": "/docs",
        "health": "/api/v1/health",
    }


# Health check at root level
@app.get("/health")
async def health():
    """Quick health check"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
