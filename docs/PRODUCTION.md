# VectorBrain — Production Configuration

How the application is configured for production, and what each setting does.
For step-by-step deploy instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).

## Architecture (production)

```
browser ──► nginx (:80, frontend container)
               ├── /            → static SPA (built with `npm run build`)
               └── /api/        → reverse proxy → backend:8000 (uvicorn, 2 workers)
                                                        └──► postgres:5432 (pgvector)
                                                        └──► Groq API (https)
```

The SPA calls the API at the **same-origin `/api` path**. The browser never
needs a baked-in backend URL, so CORS is a non-issue in production and the
frontend image needs no build-time configuration.

## Backend environment variables

All settings are environment-driven (12-factor). Copy
`backend/.env.example` to `backend/.env` for local dev; in production, inject
them via the container environment — **never commit real values**.

| Variable | Default | Production guidance |
|---|---|---|
| `ENV` | `dev` | Set to `prod`. Enables JSON logs and disables `/docs` and `/redoc`. |
| `LOG_LEVEL` | `INFO` | `INFO` is right for prod; `DEBUG` only when troubleshooting. |
| `APP_NAME` | `VectorBrain` | Cosmetic. |
| `DATABASE_URL` | `postgresql+asyncpg://vectorbrain:vectorbrain@localhost:5432/vectorbrain` | Point at the production Postgres. The password must be a strong generated secret, different from dev. |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Only needed if the SPA and API are served from **different origins**. With the default nginx `/api/` proxy (same origin), CORS is never exercised. If you split them, set this to the exact frontend origin(s), e.g. `["https://app.example.com"]`. Never `*` with credentials. |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Changing this requires re-ingesting all documents: embeddings are 384-dim and stored, not recomputed. |
| `UPLOAD_DIR` | `/data/uploads` | Must be a persistent volume in production (the compose prod file mounts a named volume). Files are referenced by the database; losing them orphans retry/reprocessing. |
| `MAX_FILE_MB` | `50` | Per-file cap, enforced while streaming (a huge upload can never fill memory). nginx's `client_max_body_size` is set to match (`520m`). |
| `MAX_FILES_PER_REQUEST` | `10` | Batch cap per upload request. |
| `CHUNK_MAX_TOKENS` | `512` | HybridChunker ceiling; affects retrieval granularity, not quality-critical. |
| `GROQ_API_KEY` | _(none)_ | **Required for Q&A.** Server-side only: it is sent solely as an `Authorization` header to Groq, never logged, never returned by the API, never embedded in the frontend bundle. Without it, `/api/v1/chat/query` returns `503 LLM_NOT_CONFIGURED` (documents remain uploadable/searchable). |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Model name is config, not code — Groq retires models over time. |
| `GROQ_TIMEOUT_SECONDS` | `60` | Upstream LLM timeout; timeouts surface as `502` with the standard error envelope. |
| `RETRIEVAL_TOP_K` | `8` | Chunks retrieved per question (client may request 1–20). |
| `RAG_MAX_CONTEXT_TOKENS` | `6000` | Token budget for retrieved context packed into the prompt. |
| `LLM_MAX_TOKENS` | `1024` | Cap on the generated answer length. |
| `LLM_TEMPERATURE` | `0.2` | Low on purpose: grounded answers should not improvise. |
| `RATE_LIMIT_QUERY_PER_MIN` | `20` | Per-IP rate limit on the chat endpoint (paid upstream API). Behind the nginx proxy the real client IP is recovered from `X-Forwarded-For` (`--proxy-headers` + nginx `proxy_set_header`s). |

## Frontend configuration

The frontend has **no runtime configuration** — it is a static bundle.

- API base URL defaults to same-origin `/api` (works in dev via the Vite
  proxy and in prod via the nginx proxy).
- `VITE_API_BASE_URL` (build-time, see `frontend/.env.example`) is only
  needed when the API lives on a different origin — then `CORS_ORIGINS`
  must allow the frontend origin.
- Never put secrets in `VITE_*` variables: they are embedded in the bundle.

## Security posture

- **Secrets**: `GROQ_API_KEY` and the Postgres password travel via environment
  only. Both `.env` files are gitignored; `.env.example` files carry no real
  values. The frontend bundle contains no keys (verified: the key is only
  ever placed in an `Authorization` header server-side).
- **Uploads**: PDFs are validated by magic bytes (`%PDF-`), size-capped while
  streaming, rejected if encrypted, stored as `{uuid}.pdf` (original filename
  never touches the filesystem — no path traversal), and SHA-256 deduplicated.
- **API surface**: `/docs` and `/redoc` are disabled when `ENV=prod`. All
  errors — including Pydantic 422s and unexpected 500s — return the same
  JSON envelope (`code`, `message`, `request_id`); tracebacks go to server
  logs only, never to the client. Ingestion failure messages are sanitized
  (internal paths stripped).
- **Abuse**: chat is rate-limited per IP (default 20/min); uploads are
  size- and count-capped.
- **Headers** (nginx): `X-Content-Type-Options: nosniff`, `X-Frame-Options:
  DENY`, `Referrer-Policy: no-referrer`, and a restrictive CSP
  (`connect-src 'self'`).
- **Network**: the prod compose file publishes only port 80. Postgres and the
  backend are reachable only inside the compose network.

## Performance characteristics

- **Embeddings**: `all-MiniLM-L6-v2` (384-dim) runs on CPU, batched at 32
  texts; generation happens in background tasks so uploads return `202`
  immediately.
- **Retrieval**: pgvector HNSW index on `chunks.embedding` with
  `vector_cosine_ops`; queries filter to `processed` documents only and
  default to `top_k=8`.
- **LLM**: single Groq call per question with a 60 s timeout and one retry on
  429/5xx. No streaming (answers are short and cited).
- **DB connections**: asyncpg pool (`pool_size=5`, `max_overflow=10`,
  `pool_pre_ping=True`), one engine per uvicorn worker.
- **Frontend**: the documents list and question input make no polling calls
  except per-document status polling (2 s) while a file is `pending` /
  `processing`; polling stops as soon as the document settles.
