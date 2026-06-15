# SpecForge Backend

An AI-native product management backend that turns raw customer signal — interviews, support
tickets, feedback — into agent-executable Product Requirements Documents (PRDs).

Raw text or PDFs go in. A ranked list of customer pain points comes out. A PM approves the
ones that matter. A structured, Pydantic-validated PRD (with user stories, acceptance criteria,
edge cases, schema sketch, and a ready-to-paste Claude Code prompt) comes out the other end.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.14 |
| Package manager | [uv](https://docs.astral.sh/uv/) |
| Framework | FastAPI |
| Database | NeonDB (PostgreSQL + pgvector, cloud-hosted) |
| Embeddings | Voyage AI `voyage-3` (1024-dim) |
| LLM | Groq `llama-3.3-70b-versatile` |
| Pipeline orchestration | LangGraph `StateGraph` |
| Auth | JWT (`python-jose`) + bcrypt |
| ORM | SQLAlchemy (async) |
| Migrations | Alembic |

---

## Project Structure

```
backend/
├── main.py                        # FastAPI app factory + router registration
├── pyproject.toml                 # Dependencies & metadata (source of truth)
├── alembic.ini
├── alembic/
│   └── versions/                  # Migration history (4 migrations, Phases 0–4)
│
└── app/
    ├── core/
    │   ├── config.py              # pydantic-settings config (reads .env)
    │   ├── database.py            # Async SQLAlchemy engine + session factory
    │   └── security.py            # JWT creation, bcrypt hashing, get_current_user dep
    │
    ├── models/                    # SQLAlchemy ORM models
    │   ├── user.py
    │   ├── project.py
    │   ├── signal.py
    │   ├── signal_chunk.py        # Vector[1024] embedding column
    │   ├── pipeline_run.py        # status + prd_json (JSON column)
    │   └── opportunity.py         # scored + approvable cluster themes
    │
    ├── routers/
    │   ├── auth.py                # register, login
    │   ├── projects.py            # CRUD
    │   ├── signals.py             # ingest PDF / plain text
    │   ├── pipeline.py            # trigger run, poll status, approve
    │   ├── opportunities.py       # list & edit ranked themes
    │   └── prd.py                 # retrieve structured PRD + markdown export
    │
    ├── schemas/
    │   ├── auth.py
    │   ├── projects.py
    │   ├── signals.py
    │   ├── pipeline.py            # PipelineRunOut, OpportunityOut, OpportunityUpdate
    │   └── prd.py                 # UserStory, PRDDocument, PRDOut
    │
    ├── pipeline/
    │   ├── state.py               # PipelineState TypedDict
    │   ├── graph.py               # StateGraph: ingest→cluster→score→[interrupt]→generate
    │   └── nodes/
    │       ├── ingest.py          # load embedded chunks from DB
    │       ├── cluster.py         # cosine similarity → Groq labels
    │       ├── score.py           # frequency + severity → Opportunity rows
    │       └── generate.py        # approved themes → PRDDocument (Groq)
    │
    └── services/
        ├── llm.py                 # Groq async client (structured JSON output)
        ├── embeddings.py          # Voyage AI async client
        ├── pdf.py                 # pypdf text extraction
        └── chunking.py            # paragraph + sentence splitting (≤800 chars)
```

---

## Setup

**Prerequisites:** Python 3.14, [uv](https://docs.astral.sh/uv/) installed.

```bash
# 1. Clone and install dependencies
git clone <repo-url>
cd backend
uv sync

# 2. Configure environment
cp .env.example .env
# Edit .env and fill in the four required variables (see table below)

# 3. Apply database migrations
uv run alembic upgrade head

# 4. Start the server
uv run python main.py
# Server runs at http://localhost:8000
# Swagger UI at http://localhost:8000/docs
```

---

## Environment Variables

Create a `.env` file at the repo root. All four variables are required.

| Variable | Description |
|---|---|
| `DATABASE_URL` | NeonDB connection string: `postgresql+asyncpg://user:pass@host/db` (pgvector must be enabled in the Neon dashboard) |
| `GROQ_API_KEY` | Groq API key — used for `llama-3.3-70b-versatile` LLM calls |
| `JWT_SECRET_KEY` | Arbitrary secret string used to sign and verify JWT tokens |
| `VOYAGE_API_KEY` | Voyage AI API key — used for `voyage-3` embedding generation |

---

## API Reference

All endpoints except `/health`, `/auth/register`, and `/auth/login` require a
`Authorization: Bearer <token>` header.

Full interactive docs: `http://localhost:8000/docs`

### Auth — `/auth`

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Create account → `UserOut` |
| POST | `/auth/login` | Authenticate → `TokenResponse` (JWT) |

### Projects — `/projects`

| Method | Path | Description |
|---|---|---|
| POST | `/projects` | Create project → `ProjectOut` |
| GET | `/projects` | List your projects |
| GET | `/projects/{project_id}` | Get project |
| PUT | `/projects/{project_id}` | Update name / description |
| DELETE | `/projects/{project_id}` | Delete project (cascades to all data) |

### Signals — `/projects/{project_id}/signals`

| Method | Path | Description |
|---|---|---|
| POST | `.../signals/text` | Ingest plain text signal |
| POST | `.../signals/upload` | Ingest PDF (multipart upload) |
| GET | `.../signals` | List signals for project |
| GET | `.../signals/{signal_id}` | Get signal details |

### Pipeline — `/projects/{project_id}/pipeline`

| Method | Path | Description |
|---|---|---|
| POST | `.../pipeline/run` | Trigger pipeline run → `{run_id, status: "pending"}` |
| GET | `.../pipeline/{run_id}/status` | Poll status + opportunities list |
| POST | `.../pipeline/{run_id}/approve` | Resume pipeline after PM review |

### Opportunities — `/projects/{project_id}/pipeline/{run_id}/opportunities`

| Method | Path | Description |
|---|---|---|
| GET | `/` | List ranked opportunities (sorted by `total_score` DESC) |
| PATCH | `/{opportunity_id}` | Edit label, description, severity score, or approval flag |

### PRD — `/projects/{project_id}/pipeline/{run_id}/prd`

| Method | Path | Description |
|---|---|---|
| GET | `/` | Retrieve structured PRD as JSON (`PRDOut`) |
| GET | `/export` | Export PRD as plain-text markdown |

---

## End-to-End Workflow

### Step 1 — Register & Login

```
POST /auth/register   { "email": "pm@co.com", "password": "..." }
POST /auth/login      { "email": "pm@co.com", "password": "..." }
                   →  { "access_token": "<jwt>", "token_type": "bearer" }
```

Use `access_token` as `Authorization: Bearer <token>` on all subsequent requests.

---

### Step 2 — Create a Project

```
POST /projects   { "name": "Dark Mode Feature" }
              →  { "id": "<project_id>", "name": "Dark Mode Feature", ... }
```

---

### Step 3 — Ingest Customer Signals

Upload every relevant source: user interviews, support tickets, NPS responses, Slack threads.

```
# Plain text
POST /projects/{project_id}/signals/text
  { "content": "Users keep asking for dark mode. It hurts their eyes at night..." }

# PDF transcript
POST /projects/{project_id}/signals/upload
  multipart file upload
```

**What happens internally:**
1. Text is extracted (PDF via pypdf, or used directly)
2. Split into atomic feedback chunks (paragraph → sentence fallback, ≤800 chars, ≥30 chars)
3. Each chunk embedded with Voyage AI `voyage-3` → 1024-dimensional vector
4. Stored in `signal_chunks` with a pgvector column

Repeat for as many signals as needed. More signal = better clustering.

---

### Step 4 — Trigger the Pipeline

```
POST /projects/{project_id}/pipeline/run
  →  { "id": "<run_id>", "status": "pending", ... }
```

The pipeline runs as a FastAPI background task (the HTTP response returns immediately).

**Node chain:**

```
ingest  →  cluster  →  score  →  [INTERRUPT]  →  generate
```

| Node | What it does |
|---|---|
| **ingest** | Loads all `signal_chunks` with embeddings for the project from the DB |
| **cluster** | Builds a cosine-similarity matrix (numpy), groups chunks with greedy clustering at a 0.72 threshold, calls Groq once per cluster to generate a human-readable label and description |
| **score** | Calls Groq once per cluster to rate severity (1–10); computes `frequency_score = cluster_size / total_chunks`; `total_score = 0.6 × frequency + 0.4 × (severity / 10)`; writes `Opportunity` rows to the DB |
| **[INTERRUPT]** | Graph pauses here — status becomes `awaiting_approval`. PM reviews before anything is generated. |

**Poll until the pipeline is ready for review:**

```
GET /projects/{project_id}/pipeline/{run_id}/status
  →  { "status": "awaiting_approval", "opportunities": [...] }
```

---

### Step 5 — Review & Approve Opportunities

The pipeline surfaces ranked themes from the customer signal. Review, adjust, and approve.

```
# 1. See all ranked opportunities
GET /projects/{project_id}/pipeline/{run_id}/opportunities
  →  [
       { "label": "Dark mode request", "total_score": 0.81, "is_approved": null, ... },
       { "label": "Slow load times", "total_score": 0.64, "is_approved": null, ... },
       ...
     ]

# 2. Optionally edit a label, description, or severity score
PATCH /projects/{project_id}/pipeline/{run_id}/opportunities/{opportunity_id}
  { "severity_score": 8, "is_approved": true }

# 3. Resume the pipeline (at least one opportunity must be approved)
POST /projects/{project_id}/pipeline/{run_id}/approve
  →  { "status": "generating" }
```

Only the approved opportunities are passed to the PRD generation step. `severity_score` must
be between 1 and 10; setting it recalculates `total_score` automatically.

---

### Step 6 — PRD Generation

The graph resumes at the `generate` node. Groq receives the approved opportunity labels and
descriptions and returns a fully structured PRD, validated against the `PRDDocument` Pydantic
schema before being stored. Free-form text is never stored.

**Poll until complete:**

```
GET /projects/{project_id}/pipeline/{run_id}/status
  →  { "status": "completed", ... }
```

**Retrieve the structured PRD:**

```
GET /projects/{project_id}/pipeline/{run_id}/prd
```

```json
{
  "run_id": "...",
  "prd": {
    "summary": "Users want a system-aware dark mode to reduce eye strain...",
    "user_stories": [
      {
        "title": "Toggle dark mode",
        "as_a": "user working late",
        "i_want": "to switch to dark mode",
        "so_that": "my eyes are not strained by a bright screen",
        "acceptance_criteria": [
          "A toggle appears in user settings",
          "Preference persists across sessions",
          "System preference is respected by default"
        ]
      }
    ],
    "edge_cases": [
      "User has no system preference set",
      "Dark mode toggled while on a page with custom brand colors"
    ],
    "schema_sketch": "users.theme_preference (enum: light|dark|system)",
    "claude_code_prompt": "Implement a dark mode toggle for a React + FastAPI app..."
  }
}
```

**Export as markdown:**

```
GET /projects/{project_id}/pipeline/{run_id}/prd/export
  →  text/plain  (full rendered PRD document)
```

---

## Pipeline Architecture

### State

All nodes share a `PipelineState` TypedDict threaded through the LangGraph graph:

```python
class PipelineState(TypedDict):
    project_id: str
    run_id: str
    chunks: list[dict]        # {id, content, embedding: list[float]}
    clusters: list[dict]      # {label, description, chunk_ids}
    opportunities: list[dict] # scored cluster summaries
    error: str | None
```

### Human Checkpoint

The graph is compiled with `interrupt_before=["generate"]`:

```python
pipeline_graph = graph.compile(
    checkpointer=MemorySaver(),
    interrupt_before=["generate"],
)
```

- `MemorySaver` stores the full pipeline state in-memory, keyed by `thread_id = run_id`
- The graph pauses after `score`, before `generate`
- When the PM calls `/approve`, the background task calls `astream(None, config)` with the
  same `thread_id` — LangGraph resumes from the saved checkpoint at the `generate` node
- **Note:** `MemorySaver` state is lost on server restart (zero-infrastructure tradeoff)

### LLM Calls

All LLM calls go through `app/services/llm.py`:

```python
result = await structured_completion(prompt, MyPydanticSchema)
```

Uses `response_format={"type": "json_object"}` + `model_validate_json()` — every LLM output
is Pydantic-validated before it touches the database.

---

## Running Tests

```bash
uv run pytest           # run all tests
uv run pytest -v        # verbose output
```

Current coverage: `/health`, auth register/login, duplicate email guard.

---

## Database Migrations

```bash
# Apply all pending migrations
uv run alembic upgrade head

# Create a new migration (after modifying a model)
uv run alembic revision --autogenerate -m "describe the change"

# Downgrade one step
uv run alembic downgrade -1
```

Migration history:
1. `4d51133d0bdd` — create users table
2. `e925b8f6e000` — add projects, signals, signal_chunks (pgvector)
3. `ec842cb13056` — add pipeline_runs, opportunities
4. `f21d9511bf46` — replace `prd_text` (Text) with `prd_json` (JSON)
