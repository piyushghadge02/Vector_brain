# VectorBrain — Phase 6 Integration Report

Date: 2026-10-06. All steps below ran against real services: PostgreSQL 16 +
pgvector, FastAPI, the production Vue build, real Docling/MiniLM ingestion,
and the real Groq API (`openai/gpt-oss-120b`).

## Workflow results (16/16 checks passed)

| # | Step | Result |
|---|------|--------|
| 1 | Start PostgreSQL | OK (local pgserver cluster, fresh `vectorbrain_e2e` DB, alembic `head`) |
| 2 | Start FastAPI | OK (`/api/health` → 200, pgvector available) |
| 3 | Start Vue frontend | OK (production build served, HTTP 200) |
| 4 | Upload PDF 1 (`zyvorg.pdf`, fictional synthesizer) | 202 accepted |
| 5 | Upload PDF 2 (`tides.pdf`, ocean tides) | 202 accepted |
| 6 | Both appear in document list | OK (`GET /v1/documents`) |
| 7 | Both processed and stored | OK — 1 page / 1 chunk each, 384-dim embeddings in pgvector |
| 8–10 | Q: "Who invented the Zylorg synthesizer and when?" | Correct ("Dr. Elena Voss", "1974"), cites `zyvorg.pdf` |
| 11–12 | Q: "What causes ocean tides, and where are the highest tides?" | Correct ("Moon", "Bay of Fundy"), cites `tides.pdf` |
| 13–14 | Q: "Who invented the Zylorg synthesizer, and what causes ocean tides?" | Both facts answered, cites **both** documents |
| 15–16 | Q: "What is the boiling point of tungsten?" (unrelated) | No hallucination — exact "not enough information" response, zero sources |
| 17 | Delete `zyvorg.pdf` | 204 |
| 18 | Document + chunks handled correctly | Doc → 404; chunk rows cascade-deleted (1 chunk left, belonging to `tides.pdf`); re-asking Q1 now returns "not enough information" with no citation of the removed doc |

## Integration issue found and fixed

**gpt-oss renders citations as ``, not `[n]`.** The first live Groq call
returned a correct, grounded answer citing `` — but the citation parser
only recognized ASCII `[n]`, so `sources` came back empty. Fixed in two places:

- `backend/app/services/rag.py` — `extract_citations` now accepts both
`[n]` and ``; system prompt explicitly demands ASCII `[n]`.
- `frontend/src/components/ChatMessage.vue` — citation highlighter accepts both styles.

Added a unit test (`test_extract_citations_accepts_cjk_brackets`). After the
fix, citations map correctly in both styles (observed live in Q1/Q3).

## Verification battery

- Backend tests: **66 passed**, 2 deselected (`real_model`, need key-free CI)
- `ruff check` / `ruff format --check`: clean
- Frontend: `vue-tsc` typecheck + `vite build`: clean
- API-integration script (`e2e/workflow.mjs`, replicates the frontend's exact
API calls): **16/16**; earlier `e2e/api-integration.mjs`: 10/10
- Interactive browser E2E was not possible in this sandbox (hardened Chromium
blocks all loopback; no working tunnel through the egress proxy). The
workflow script covers the same flows at the API layer.

## Notes

- The Groq API key was used **transiently** (process environment only, never
written to disk, repo, or logs) and has been discarded. To run Q&A again,
set `GROQ_API_KEY` in `backend/.env` (gitignored).
- Sandbox quirk: backend/test processes need
`no_proxy=localhost,127.0.0.1` or Docling's HuggingFace download crashes
(httpx bracketed-IPv6 parsing bug). See `~/TOOLS.md`.
- E2E scripts kept in `e2e/` (`workflow.mjs` full run, `api-integration.mjs`
contract checks, `run.mjs` browser script for non-sandboxed machines).
