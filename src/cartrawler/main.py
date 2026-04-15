"""
CarTrawler MCP Server — Application Entry Point
================================================
Runs the FastMCP server over HTTP (SSE transport) so ChatGPT's
Custom Connector / MCP Inspector can reach it.

Start:
    uv run cartrawler-server          # via pyproject.toml script
    uv run python -m cartrawler.main  # direct
    uvicorn cartrawler.main:app       # ASGI runner
"""
from __future__ import annotations

import logging
import os

import uvicorn

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from cartrawler.auth.oauth import (
    oauth_authorize, oauth_metadata, oauth_register, oauth_token,
)
from cartrawler.config import settings
from cartrawler.mcp_server import create_mcp_app, create_mcp_http_app

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("cartrawler")

# ─────────────────────────────────────────────────────────────────────────────
# ASGI app (importable by uvicorn / gunicorn)
# ─────────────────────────────────────────────────────────────────────────────

async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "cartrawler-mcp"})


async def admin_dbcheck(_request: Request) -> JSONResponse:
    """GET /admin/dbcheck — verify DB connectivity and show sanitised URL."""
    from sqlalchemy import text
    from cartrawler.db.database import engine

    url = settings.database_url
    # Hide password in response
    try:
        from urllib.parse import urlparse, urlunparse
        p = urlparse(url)
        safe_url = urlunparse(p._replace(netloc=f"{p.username}:***@{p.hostname}:{p.port}"))
    except Exception:
        safe_url = url[:40] + "…"

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return JSONResponse({"db": "ok", "url": safe_url})
    except Exception as exc:
        return JSONResponse({"db": "error", "url": safe_url, "error": str(exc)}, status_code=500)


async def admin_seed(request: Request) -> JSONResponse:
    """
    POST /admin/seed
    Header: Authorization: Bearer <SEED_SECRET>

    Drops all tables, recreates them, and seeds from the CSV files in data/.
    Protected by SEED_SECRET env var — never call without setting it.
    """
    seed_secret = os.environ.get("SEED_SECRET", "")
    if not seed_secret:
        return JSONResponse(
            {"error": "SEED_SECRET env var not set on this server"},
            status_code=503,
        )

    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {seed_secret}":
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    try:
        from cartrawler.admin.seeder import run_seed
        logger.info("Starting database seed…")
        results = await run_seed()
        logger.info("Database seed complete.")
        return JSONResponse({
            "status": "ok",
            "message": "Database dropped and re-seeded successfully.",
            "rows": results,
        })
    except Exception as exc:
        logger.exception("Seed failed: %s", exc)
        return JSONResponse({"status": "error", "message": str(exc)}, status_code=500)


async def admin_embed(request: Request) -> JSONResponse:
    """
    POST /admin/embed
    Header: Authorization: Bearer <SEED_SECRET>

    Generates OpenAI embeddings for all knowledge_base rows and stores
    them in knowledge_base_embeddings for RAG-powered FAQ queries.
    """
    seed_secret = os.environ.get("SEED_SECRET", "")
    if not seed_secret:
        return JSONResponse({"error": "SEED_SECRET env var not set"}, status_code=503)
    if request.headers.get("Authorization") != f"Bearer {seed_secret}":
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    try:
        from cartrawler.admin.embedder import run_embed
        logger.info("Starting embedding build…")
        result = await run_embed(rebuild=True)
        logger.info("Embedding complete: %s", result)
        return JSONResponse({"status": "ok", **result})
    except Exception as exc:
        logger.exception("Embed failed: %s", exc)
        return JSONResponse({"status": "error", "message": str(exc)}, status_code=500)


_mcp_sse_app  = create_mcp_app()       # SSE  — ChatGPT Custom Connector (/sse)
_mcp_http_app = create_mcp_http_app()  # Streamable HTTP — ChatGPT Apps UI (/mcp)

# Inject SSE routes directly — avoids Starlette path-stripping bug with Mount("/")
# _mcp_sse_app.routes = [Route('/sse', ...), Mount('/messages', ...)]
app = Starlette(
    routes=[
        Route("/health",        health),
        Route("/admin/dbcheck", admin_dbcheck),
        Route("/admin/seed",    admin_seed,  methods=["POST"]),
        Route("/admin/embed",   admin_embed, methods=["POST"]),
        # OAuth 2.0 + PKCE — required by ChatGPT Apps UI
        Route("/.well-known/oauth-authorization-server", oauth_metadata),
        Route("/oauth/register",  oauth_register,  methods=["POST"]),
        Route("/oauth/authorize", oauth_authorize, methods=["GET", "POST"]),
        Route("/oauth/token",     oauth_token,     methods=["POST"]),
        Mount("/mcp",  app=_mcp_http_app),   # Streamable HTTP for ChatGPT Apps UI
        *_mcp_sse_app.routes,                # /sse (GET) + /messages (POST) — direct, no stripping
    ]
)

# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

def run_server() -> None:
    """Start the MCP server (called by `cartrawler-server` script)."""
    logger.info("Starting CarTrawler MCP Server")
    logger.info("  Host : %s", settings.mcp_server_host)
    logger.info("  Port : %s", settings.mcp_server_port)
    logger.info("  Env  : %s", settings.app_env)
    logger.info("  Model: %s", settings.openai_model)

    uvicorn.run(
        "cartrawler.main:app",
        host=settings.mcp_server_host,
        port=settings.mcp_server_port,
        reload=settings.debug and not settings.is_production,
        log_level="debug" if settings.debug else "info",
        access_log=True,
    )


if __name__ == "__main__":
    run_server()
