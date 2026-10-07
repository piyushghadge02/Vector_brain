# Knowledge Bytes — API and End-to-End Data Flow

### Byte 1: Browser-to-Backend Boundary
**Builds on:** Backend Byte 1

**In plain terms:**
The browser communicates with FastAPI through HTTP API routes. The frontend does not directly connect to PostgreSQL or Groq.

**The code:**
```text
Vue
 ↓ HTTP
FastAPI
 ↓
DB / Docling / Groq
```

What's happening:
FastAPI is the controlled boundary for application operations.

Why it matters:
It keeps credentials and internal services away from the browser.

---

### Byte 2: Upload-to-Search Flow
**Builds on:** Document Processing + Embeddings

**In plain terms:**
Uploading a document triggers the ingestion path that ultimately creates searchable knowledge.

**The code:**
```text
PDF
→ API
→ processing
→ chunks
→ embeddings
→ PostgreSQL
```

What's happening:
The stored vectors are what later allow semantic retrieval.

Why it matters:
A document is not ready for questions until ingestion has completed successfully.

---

### Byte 3: Question-to-Answer Flow
**Builds on:** RAG + Groq

**In plain terms:**
A question travels through retrieval and generation before the answer returns to the browser.

**The code:**
```text
Question
→ API
→ query embedding
→ vector search
→ context
→ Groq
→ answer + sources
→ Vue
```

What's happening:
Every stage has a distinct responsibility.

Why it matters:
This flow provides a systematic debugging path when answers fail.
