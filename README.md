# VectorBrain — Multi-Document AI Research Assistant

A "second brain" for studying: upload multiple PDFs, ask questions across **all**
of them, and get grounded answers with source citations — powered by RAG over
PostgreSQL + pgvector.

**Status:** Phase 1 (project foundation) — see [PROJECT_PLAN.md](PROJECT_PLAN.md)
for the full architecture and phased implementation plan.

## Tech stack

| Layer      | Technology                                                        |
|------------|-------------------------------------------------------------------|
| Frontend   | Vue 3 + Vite + TypeScript, Pinia, Vue Router, Tailwind CSS, Axios |
| Backend    | FastAPI (Python 3.11+), Pydantic v2, SQLAlchemy 2.0 (async)       |
| Database   | PostgreSQL 16 + pgvector (384-dim HNSW cosine search)             |
| PDF parsing| Docling *(Phase 3)*                                               |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2`, 384-dim *(Phase 3)*     |
| LLM        | Groq API, server-side only *(Phase 4)*                            |

## Quickstart (Docker Compose)

```bash
# 1. Start everything (postgres, backend, frontend)
docker compose up --build

# 2. In another terminal, run the database migrations
docker compose exec backend alembic upgrade head

# 3. Open the app
#    frontend → http://localhost:5173
#    API docs → http://localhost:8000/docs
#    health   → http://localhost:8000/api/health
```

No `.env` files are needed for the default local setup — sane defaults are
baked into `docker-compose.yml`.

## Manual setup (without Docker)

**Backend**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # adjust DATABASE_URL to your Postgres
alembic upgrade head
uvicorn app.main:app --reload
```

You need PostgreSQL 16 with the pgvector extension installed.

**Frontend**

```bash
cd frontend
cp .env.example .env   # set VITE_API_BASE_URL if the API isn't on localhost:8000
npm install
npm run dev
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://…@localhost:5432/vectorbrain` | Async Postgres URL |
| `ENV` | `dev` | `dev` \| `prod` \| `test` (prod enables JSON logs, disables `/docs`) |
| `LOG_LEVEL` | `INFO` | Python log level |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed browser origins |
| `GROQ_API_KEY` | _(empty)_ | Groq key — **server-side only, never in the frontend** *(Phase 4)* |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Model name is config, not code *(Phase 4)* |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | 384-dim embeddings *(Phase 2)* |
| `VITE_API_BASE_URL` | `http://localhost:8000/api` | Backend URL for the browser (frontend) |

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Liveness + dependency status (DB, pgvector) |
| `POST` | `/api/v1/documents/upload` | Upload 1–10 PDFs (multipart); returns 202, processing runs in background |
| `GET` | `/api/v1/documents` | Paginated list with metadata + ingestion status (`?status=&page=&size=`) |
| `GET` | `/api/v1/documents/{id}` | One document's metadata + status |
| `POST` | `/api/v1/documents/{id}/retry` | Re-enqueue a failed document (202) |
| `DELETE` | `/api/v1/documents/{id}` | Delete document, chunks, and file (204) |

Document lifecycle: `pending → processing → processed` (or `failed` with a
user-safe `error_message`). Duplicate uploads (same SHA-256) return `409`
with the existing document's id. Interactive docs: `http://localhost:8000/docs`.

The chat/RAG contract is defined in `PROJECT_PLAN.md` §8 and lands in Phase 4.

Errors always use the envelope `{ "code", "message", "request_id" }`.

## Project structure

```
vectorbrain/
├── backend/            # FastAPI app (api → services → repositories)
│   ├── app/            # main.py, config.py, api/, core/, db/, schemas/
│   ├── alembic/        # DB migrations (0001: pgvector + full schema)
│   └── tests/          # unit + integration (pytest)
├── frontend/           # Vue 3 SPA (api/, stores/, router/, views/, components/)
├── docker-compose.yml  # dev: db + backend + frontend
├── docker-compose.prod.yml
└── PROJECT_PLAN.md     # authoritative architecture & phase plan
```

## Testing

```bash
# Backend (needs Postgres + pgvector; migrations applied)
cd backend
pip install -r requirements-test.txt   # test-only PDF fixtures
DATABASE_URL=postgresql+asyncpg://vectorbrain:vectorbrain@localhost:5432/vectorbrain_test \
  pytest -v -m "not real_model"

# Real-pipeline end-to-end (Docling + MiniLM; downloads ~100 MB once, slow)
no_proxy=localhost,127.0.0.1 NO_PROXY=localhost,127.0.0.1 \
DATABASE_URL=postgresql+asyncpg://vectorbrain:vectorbrain@localhost:5432/vectorbrain_test \
  pytest -m real_model

# Frontend
cd frontend
npm run build          # also runs vue-tsc typecheck
```

## Privacy note

Uploaded document text is stored in **your** PostgreSQL database. In Phase 4,
retrieved chunks are sent to the Groq API solely to generate answers — the
Groq API key never leaves the server and is never bundled into the frontend.

## Roadmap

- [x] **Phase 1** — foundation: repo, config, DB schema, Docker, health, CI
- [x] **Phase 2** — repository layer: documents/chunks CRUD + pgvector search
- [x] **Phase 3** — PDF upload & ingestion (Docling → chunks → pgvector)
- [x] **Phase 4** — semantic search + RAG: question embedding → pgvector retrieval → Groq grounded answers + citations (`POST /api/v1/chat/query`)
- [x] **Phase 5** — workspace UI: document sidebar (multi-PDF upload, status, delete) + chat with cited sources (`/`)
- [x] **Phase 6** — end-to-end integration: real DB + Docling + MiniLM + live Groq verification (`INTEGRATION_REPORT.md`)
- [x] **Phase 7** — production hardening: security/backend/frontend/DB/performance audit, fixes, [production config](docs/PRODUCTION.md) + [deployment guide](docs/DEPLOYMENT.md)

## License

MIT — see `LICENSE` (to be added in Phase 5).
