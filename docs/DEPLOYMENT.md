# VectorBrain — Deployment Guide

Production deployment with Docker Compose. Configuration reference lives in
[PRODUCTION.md](PRODUCTION.md). **Do not deploy yet** — this guide is for when
you decide to.

## Prerequisites

- A Linux host with Docker Engine + Compose v2.
- A Groq API key ([console.groq.com](https://console.groq.com)).
- (Recommended) A domain name pointing at the host, with TLS terminated in
  front of nginx (e.g. Caddy, Traefik, or a cloud load balancer). The bundled
  nginx serves plain HTTP on :80.

## First deploy

```bash
# 1. Get the code on the server
git clone <your-repo-url> vectorbrain && cd vectorbrain

# 2. Generate secrets (never reuse dev defaults)
export POSTGRES_PASSWORD=$(openssl rand -hex 24)
export GROQ_API_KEY=<redacted>

# 3. Build and start (prod override: 2 uvicorn workers, ENV=prod,
#    only port 80 published, uploads on a persistent volume)
POSTGRES_PASSWORD=$POSTGRES_PASSWORD \
GROQ_API_KEY=<redacted> \
  docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```

The base compose file reads `POSTGRES_PASSWORD` for both the db service and
the backend's `DATABASE_URL`. `GROQ_API_KEY` is consumed via the commented
line in `docker-compose.prod.yml` — uncomment it, or export the variable in
the shell as above.

```bash
# 4. Run the database migrations (once per fresh database)
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  exec backend alembic upgrade head

# 5. Verify
curl -s http://localhost/api/health
# {"status":"ok","service":"VectorBrain","env":"prod",...,"groq_configured":true}
```

Then open `http://<host>/` in a browser. The SPA is served by nginx; API
calls go to same-origin `/api/` which nginx proxies to the backend.

> **First-run latency**: the embedding model (~90 MB) downloads from
> Hugging Face on first ingestion, not at startup, so the first PDF takes
> noticeably longer to process.

## Updating to a new version

```bash
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  exec backend alembic upgrade head   # only if migrations changed
```

Uploads (`uploads` volume) and the database (`pgdata` volume) survive
rebuilds.

## Backups

Back up the Postgres data volume. Minimal approach:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  exec db pg_dump -U vectorbrain vectorbrain > backup-$(date +%F).sql
```

To be fully restorable, also back up the `uploads` volume — re-ingestion
(`POST /api/v1/documents/{id}/retry`) needs the original PDFs:

```bash
docker run --rm -v vectorbrain_uploads:/data -v "$PWD":/backup \
  alpine tar czf /backup/uploads-$(date +%F).tar.gz -C /data .
```

## Health & observability

- `GET /api/health` → `status`, `database`, `pgvector`, `embeddings`,
  `groq_configured`. The backend container has a Docker `HEALTHCHECK` on it.
- Logs are JSON when `ENV=prod` (configure your log shipper accordingly);
  every response carries an `X-Request-ID` header that also appears in error
  envelopes and server logs — include it in bug reports.
- Unexpected 500s are logged server-side with full tracebacks; clients only
  ever see `{"code":"INTERNAL_ERROR","message":"An unexpected error occurred."}`.

## Scaling notes

- uvicorn runs 2 workers in prod. Raising `--workers` is safe (each worker
  owns its engine and lazily loads its own ML models), but embedding is
  CPU-bound — scale vertically before adding workers.
- `RETRIEVAL_TOP_K`, `RAG_MAX_CONTEXT_TOKENS`, and `RATE_LIMIT_QUERY_PER_MIN`
  are the main cost/latency knobs for the Groq bill.
- For multi-host deployments, put Postgres on a managed service, point
  `DATABASE_URL` at it, and share `UPLOAD_DIR` via object storage or NFS —
  the local-volume design in this guide is single-host.

## Rollback

```bash
git checkout <previous-tag>
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  exec backend alembic downgrade -1   # only if the deploy migrated up
```
