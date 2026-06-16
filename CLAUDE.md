# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`specforge` backend — Python 3.14, managed with `uv`.

A FastAPI-based backend for SpecForge — an AI-native product management tool that turns raw
customer signal (interviews, support tickets, feedback) into agent-executable PRDs.

**Runtime LLM:** Groq llama-3.3-70b  
**Pipeline orchestration:** LangGraph  
**Database:** NeonDB (PostgreSQL + pgvector, cloud-hosted — no local DB or Docker Compose)  
**Embeddings:** Voyage AI `voyage-3` (hosted API, 1024-dim)  

---

## Commands

\```bash
# Run the app
uv run python main.py

# Add a dependency
uv add <package>

# Activate venv (if needed for direct python/pip calls)
.venv\Scripts\Activate.ps1   # PowerShell

# Run database migrations
uv run alembic upgrade head

# Create a new migration
uv run alembic revision --autogenerate -m "<description>"

# Run tests
uv run pytest
\```

\```bash
# git push command
git push -u origin main
\```

---

## Structure

\```
backend/
├── main.py                  # Entry point
├── pyproject.toml           # Source of truth for metadata and dependencies
├── alembic/                 # Database migrations
├── app/
│   ├── core/
│   │   ├── config.py        # pydantic-settings based config
│   │   ├── database.py      # Async SQLAlchemy engine + session
│   │   └── security.py      # JWT creation, hashing, get_current_user
│   ├── routers/
│   │   ├── auth.py          # register, login, Google OAuth login/callback
│   │   ├── projects.py      # CRUD for projects
│   │   ├── signals.py       # Upload/paste signal, chunking
│   │   ├── pipeline.py      # Trigger pipeline, poll status
│   │   ├── opportunities.py # List, edit, approve ranked themes
│   │   └── prd.py           # PRD retrieval, markdown export
│   ├── models/              # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic request/response schemas
│   ├── pipeline/            # LangGraph pipeline
│   │   ├── state.py         # Typed pipeline state schema
│   │   ├── graph.py         # LangGraph graph definition
│   │   └── nodes/
│   │       ├── ingest.py
│   │       ├── cluster.py
│   │       ├── score.py
│   │       └── generate.py
│   └── services/
│       ├── llm.py           # Groq LLM calls
│       ├── embeddings.py    # Embedding generation
│       ├── pdf.py           # PDF text extraction
│       └── google_oauth.py  # Google OAuth token exchange + userinfo
└── tests/
    ├── test_auth.py
    ├── test_pipeline/       # Each node tested with mocked LLM responses
    └── test_api/            # Integration tests per router
\```

> `pyproject.toml` is the source of truth for metadata and dependencies — do not use `requirements.txt`.

---

## Build Phases

### Phase 0 — Foundation
- FastAPI app factory, `pydantic-settings` config, routers folder, `/health` endpoint
- Neon Postgres connection via `DATABASE_URL` in `.env` (pgvector enabled in Neon dashboard)
- Alembic configured for async SQLAlchemy
- JWT auth: register/login, password hashing, `get_current_user` dependency
- Google OAuth: `/auth/google/login` redirects to Google, `/auth/google/callback`
  exchanges the code, finds-or-creates the user, then redirects to `FRONTEND_URL`
  with the app's own JWT

### Phase 1 — Ingestion
- ORM models: `projects`, `signals`, `signal_chunks` (pgvector column)
- Upload endpoint: PDF text extraction + plain text paste
- Chunking logic: split signal into atomic feedback units
- Embeddings generated and stored in pgvector

### Phase 2 — LangGraph Pipeline
- Typed `PipelineState` schema
- Nodes: `ingest → cluster → score → [human checkpoint] → generate`
- Cluster node: embedding similarity pre-grouping → Groq llama-3.3-70b labels/merges
- Score node: frequency from cluster size + LLM severity, Pydantic-validated output
- Human checkpoint: graph pauses awaiting PM approval via API
- Generate node: runs only post-approval
- Runs as background task with status-polling endpoint

### Phase 3 — Review & Approval API
- Endpoints: list ranked opportunities, edit scores/labels, approve/reject
- Approval resumes the LangGraph graph into the generate node

### Phase 4 — PRD Generation & Export
- Structured PRD Pydantic model: user stories, acceptance criteria, edge cases,
  schema sketch, Claude Code prompt
- LLM output validated against schema — never stored as free-form text
- Markdown export endpoint rendered from structured data

### Phase 5 — Hardening
- Unit tests for each pipeline node with mocked LLM responses
- API integration tests per router
- Auth tests
- Error handling: LLM failures, malformed PDFs, empty signal sets
- Rate limiting on LLM-heavy endpoints

---

## Key Conventions

- All LLM calls go through `app/services/llm.py` — never call Groq directly from routers or nodes
- All LLM structured outputs must be validated against a Pydantic schema before being stored
- Pipeline nodes must be independently testable with mocked inputs
- Background tasks use FastAPI's `BackgroundTasks`; pipeline status is polled via `/pipeline/{run_id}/status`
- Do not add features outside the phases above without updating this file first

---

## Environment

Required variables in `.env` (never commit this file):

| Variable         | Description                                       |
|------------------|---------------------------------------------------|
| `DATABASE_URL`   | NeonDB connection string (`postgresql+asyncpg://…`) |
| `GROQ_API_KEY`   | Groq API key for llama-3.3-70b calls              |
| `JWT_SECRET_KEY` | Secret used to sign/verify JWT tokens             |
| `VOYAGE_API_KEY` | Voyage AI API key for `voyage-3` embeddings       |
| `GOOGLE_CLIENT_ID`     | Google OAuth client ID                            |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret                        |
| `FRONTEND_URL`         | Frontend origin the Google OAuth callback redirects to |