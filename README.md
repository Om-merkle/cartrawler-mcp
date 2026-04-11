# CarTrawler MCP Server

A Model Context Protocol (MCP) server that exposes flight, car rental, hotel booking, and FAQ tools to ChatGPT via a custom connector. Built with FastMCP, FastAPI, SQLAlchemy async, Supabase (PostgreSQL), LangGraph, and OpenAI.

---

## Architecture Overview

```
ChatGPT / MCP Inspector
        │
        ▼
  FastMCP (SSE/HTTP)        ← src/cartrawler/mcp_server/server.py
        │
        ├── Auth Tools       ← register, login, logout, profile
        ├── Flight Tools     ← search, book, cancel, list bookings
        ├── Car Tools        ← search cars, book rental, rides
        ├── Hotel Tools      ← search hotels, hotel details
        ├── Offer Tools      ← list coupons, validate coupon
        ├── FAQ Tool         ← RAG-powered Q&A (pgvector)
        └── Agent Query      ← LangGraph multi-step orchestrator
                │
                ▼
        PostgreSQL (Supabase) + pgvector
```

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | >= 3.11 | [python.org](https://python.org) |
| uv | latest | `pip install uv` |
| Git | any | [git-scm.com](https://git-scm.com) |
| Supabase account | — | [supabase.com](https://supabase.com) |
| OpenAI API key | — | [platform.openai.com](https://platform.openai.com) |

---

## Step-by-Step Setup

### Step 1 — Clone the repository

```bash
git clone <your-repo-url>
cd cartrawler_openai_app
```

### Step 2 — Install dependencies

```bash
pip install uv
uv sync
```

This installs all dependencies defined in [pyproject.toml](pyproject.toml) into a virtual environment managed by `uv`.

To also install dev dependencies (pytest, ruff, mypy):

```bash
uv sync --dev
```

### Step 3 — Configure environment variables

Copy the example file and fill in your credentials:

```bash
cp .env.example .env
```

Open `.env` and set the following required values:

```env
# ── Database (from Supabase: Project Settings → Database → URI) ──
DATABASE_URL="postgresql+asyncpg://postgres:<PASSWORD>@db.<PROJECT_REF>.supabase.co:5432/postgres"
DATABASE_URL_SYNC="postgresql://postgres:<PASSWORD>@db.<PROJECT_REF>.supabase.co:5432/postgres"

# ── Supabase (from Project Settings → API) ──
SUPABASE_URL="https://<PROJECT_REF>.supabase.co"
SUPABASE_ANON_KEY="eyJ..."
SUPABASE_SERVICE_ROLE_KEY="eyJ..."

# ── OpenAI ──
OPENAI_API_KEY="sk-..."

# ── JWT (change in production) ──
JWT_SECRET_KEY="your-long-random-secret-key"
```

> **SSL note:** If you get SSL errors, append `?sslmode=require` to both database URLs.

### Step 4 — Enable pgvector on Supabase

In the Supabase dashboard, go to **SQL Editor** and run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

> pgvector is required for the RAG FAQ tool. Supabase supports it natively.

### Step 5 — Create database tables and seed data

This creates all tables and loads the CSV data files from the `data/` folder:

```bash
PYTHONPATH=src uv run python scripts/seed_db.py
```

To seed a single table only:

```bash
PYTHONPATH=src uv run python scripts/seed_db.py --table users
```

To drop and recreate all tables (destructive):

```bash
PYTHONPATH=src uv run python scripts/seed_db.py --drop
```

**Seeding order** (FK-aware): users → flights → cars → offers → bookings → search_logs → sessions → knowledge_base → hotels

### Step 6 — Build vector embeddings for the FAQ tool

This reads the `knowledge_base` table and generates OpenAI embeddings stored in `knowledge_base_embeddings` (pgvector):

```bash
PYTHONPATH=src uv run python scripts/create_embeddings.py
```

Options:

```bash
# Custom batch size (default: 20)
PYTHONPATH=src uv run python scripts/create_embeddings.py --batch 50

# Regenerate all embeddings (overwrite existing)
PYTHONPATH=src uv run python scripts/create_embeddings.py --rebuild
```

> This step requires `OPENAI_API_KEY` to be set. Only needs to run once (or when knowledge base content changes).

### Step 7 — Start the MCP server

```bash
# Option A: via project script (recommended)
PYTHONPATH=src uv run cartrawler-server

# Option B: direct Python module
PYTHONPATH=src uv run python -m cartrawler.main

# Option C: uvicorn directly
PYTHONPATH=src uv run uvicorn cartrawler.main:app --host 0.0.0.0 --port 8000 --reload
```

The server starts at: **http://localhost:8000**

---

## Verifying the Setup

### Check server health

```bash
curl http://localhost:8000/health
```

### Check available MCP tools

Open the MCP Inspector or visit:

```
http://localhost:8000/
```

### Test database connection

```bash
python -c "
import asyncio, sys
sys.path.insert(0, 'src')
from cartrawler.db.database import engine
from sqlalchemy import text

async def test():
    async with engine.connect() as conn:
        r = await conn.execute(text('SELECT COUNT(*) FROM users'))
        print('Users in DB:', r.scalar())

asyncio.run(test())
"
```

---

## Running Tests

```bash
PYTHONPATH=src uv run pytest
```

With verbose output:

```bash
PYTHONPATH=src uv run pytest -v tests/
```

---

## Project Structure

```
cartrawler_openai_app/
├── src/cartrawler/
│   ├── main.py              # App entry point + uvicorn runner
│   ├── config/
│   │   └── settings.py      # Pydantic settings (reads .env)
│   ├── db/
│   │   ├── database.py      # Async SQLAlchemy engine + session
│   │   └── models.py        # ORM table definitions
│   ├── auth/                # JWT handling, password hashing
│   ├── tools/               # MCP tool implementations
│   │   ├── auth_tools.py
│   │   ├── flight_tools.py
│   │   ├── car_tools.py
│   │   ├── hotel_tools.py
│   │   ├── offer_tools.py
│   │   └── faq_tools.py
│   ├── rag/                 # RAG pipeline + embeddings
│   ├── agent/
│   │   └── orchestrator.py  # LangGraph multi-step agent
│   └── mcp_server/
│       └── server.py        # FastMCP tool registration
├── scripts/
│   ├── seed_db.py           # Load CSV data into PostgreSQL
│   └── create_embeddings.py # Build pgvector embeddings
├── data/                    # CSV seed files
├── tests/
├── render.yaml              # Render.com deployment config
├── pyproject.toml           # Dependencies + scripts
└── .env.example             # Environment variable template
```

---

## Available MCP Tools

| Tool | Auth Required | Description |
|------|:---:|-------------|
| `register` | No | Create a new user account |
| `login` | No | Authenticate, get JWT tokens |
| `refresh_session` | No | Renew expired access token |
| `get_my_profile` | Yes | View user profile and loyalty points |
| `logout` | Yes | Invalidate session |
| `find_flights` | No | Search flights by city/IATA/class/price |
| `flight_details` | No | Full details for a specific flight |
| `book_a_flight` | Yes | Book a flight with optional coupon |
| `my_bookings` | Yes | List all bookings (filterable) |
| `my_booking` | Yes | Get a specific booking |
| `cancel_my_booking` | Yes | Cancel booking (refund if eligible) |
| `find_cars` | No | Search rental cars by city/type/vendor |
| `car_details` | No | Full details for a specific car |
| `book_rental_car` | Yes | Book a car rental |
| `my_rides` | Yes | List ride/vehicle bookings |
| `ride_details` | Yes | Get specific ride details |
| `find_hotels` | No | Search hotels by city/amenities/price |
| `hotel_details` | No | Full details for a specific hotel |
| `list_offers` | No | View all active discount coupons |
| `check_coupon` | No | Validate coupon and calculate discount |
| `best_offers_for_booking` | No | Find best offer for a booking amount |
| `faq` | No | AI-powered FAQ (RAG + pgvector) |
| `agent_query` | Optional | Multi-step LangGraph agent |

---

## Deployment on Render.com

The [render.yaml](render.yaml) is pre-configured for one-click deployment:

1. Push the repo to GitHub
2. Go to [render.com](https://render.com) → **New → Blueprint**
3. Connect your repository
4. In the Render dashboard, set the secret environment variables marked `sync: false`:
   - `DATABASE_URL`
   - `DATABASE_URL_SYNC`
   - `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
   - `OPENAI_API_KEY`
5. Deploy — the seed job runs automatically after the first deploy

Start command used by Render:

```bash
uv run uvicorn cartrawler.main:app --host 0.0.0.0 --port $PORT
```

---

## Connecting to ChatGPT

1. Start the server (locally or deployed on Render)
2. In ChatGPT, go to **Settings → Beta features → Model Context Protocol**
3. Add a new connector with the server URL:
   - Local: `http://localhost:8000`
   - Render: `https://<your-service>.onrender.com`
4. ChatGPT will discover all registered tools automatically

---

## Common Issues

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError: cartrawler` | Add `PYTHONPATH=src` before the command |
| SSL connection error | Append `?sslmode=require` to `DATABASE_URL` |
| `pgvector` extension missing | Run `CREATE EXTENSION IF NOT EXISTS vector;` in Supabase SQL editor |
| `OPENAI_API_KEY not set` | Set it in `.env` before running `create_embeddings.py` |
| Password with special characters | URL-encode them (e.g. `@` → `%40`, `#` → `%23`) |
| Supabase free tier pauses | `NullPool` in `database.py` handles reconnects automatically |
