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
import sys

import uvicorn

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

app = create_mcp_app()

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
