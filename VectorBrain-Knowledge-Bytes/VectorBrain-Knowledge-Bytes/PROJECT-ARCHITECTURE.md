# VectorBrain — Project Architecture

```text
                    ┌──────────────────────┐
                    │     Vue.js 3 UI      │
                    │ documents + chat      │
                    └──────────┬───────────┘
                               │ HTTP
                               ▼
                    ┌──────────────────────┐
                    │    FastAPI Backend   │
                    │ API + orchestration  │
                    └──────┬───────┬───────┘
                           │       │
                 ┌─────────┘       └────────────┐
                 ▼                              ▼
        ┌─────────────────┐             ┌─────────────────┐
        │ Docling /       │             │ Groq API        │
        │ ingestion       │             │ generation      │
        └────────┬────────┘             └────────▲────────┘
                 │                               │
                 ▼                               │
        ┌─────────────────────────────┐          │
        │ PostgreSQL + pgvector       │──────────┘
        │ documents / chunks / vectors│
        └─────────────────────────────┘
```

## Core user journey

1. User opens the Vue application.
2. User uploads one or more PDFs.
3. FastAPI accepts the files.
4. Docling extracts document content.
5. Content is prepared for retrieval and embedded.
6. PostgreSQL/pgvector stores searchable information.
7. User asks a question.
8. The backend embeds/retrieves relevant content.
9. Retrieved context is supplied to Groq.
10. The answer and source information return to Vue.
