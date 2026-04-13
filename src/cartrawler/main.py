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
from pathlib import Path

import uvicorn

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from cartrawler.config import settings
from cartrawler.mcp_server import create_mcp_app

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

    # Load seed_db from scripts/ using explicit file path (avoids import resolution issues)
    # src/cartrawler/main.py → parents[2] = repo root
    seed_file = Path(__file__).resolve().parents[2] / "scripts" / "seed_db.py"

    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("seed_db", seed_file)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Could not load {seed_file}")
        seed_db = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(seed_db)  # type: ignore[union-attr]
        logger.info("Starting database seed (drop=True)…")
        await seed_db._run(seed_db.SEED_ORDER, drop=True)
        logger.info("Database seed complete.")
        return JSONResponse({
            "status": "ok",
            "message": "Database dropped and re-seeded successfully.",
            "tables": seed_db.SEED_ORDER,
        })
    except Exception as exc:
        logger.exception("Seed failed: %s", exc)
        return JSONResponse({"status": "error", "message": str(exc)}, status_code=500)


_mcp_app = create_mcp_app()

app = Starlette(
    routes=[
        Route("/health", health),
        Route("/admin/seed", admin_seed, methods=["POST"]),
        Mount("/", app=_mcp_app),
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
