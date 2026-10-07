# Knowledge Bytes — FastAPI Backend

### Byte 1: Why the Backend Exists
**Builds on:** Project Overview

**In plain terms:**
The FastAPI backend is the central coordinator between the browser, document-processing pipeline, database, vector search, and Groq.

**The code:**
```text
Frontend
   ↓ HTTP
FastAPI
 ├── documents
 ├── retrieval
 ├── database
 └── generation
```

What's happening:
The API provides stable boundaries so the frontend does not need to know how PDFs are processed or how vectors are searched.

Why it matters:
This separation makes the system easier to test, deploy, and change.

---

### Byte 2: Upload Flow
**Builds on:** Byte 1

**In plain terms:**
An upload request starts the document-ingestion workflow. The backend receives the file, stores/processes it, and eventually makes its content available for retrieval.

**The code:**
```text
POST /api/...upload...
        ↓
validate file
        ↓
store file
        ↓
process document
        ↓
persist searchable data
```

What's happening:
The exact endpoint and implementation should be taken from the repository source when generating file-specific bytes.

Why it matters:
A failure anywhere in this chain can leave a document stuck in processing or marked failed.

---

### Byte 3: Query Flow
**Builds on:** Byte 2

**In plain terms:**
A chat request causes the backend to retrieve relevant document content and pass that context to the answer-generation layer.

**The code:**
```text
POST /api/chat
   ↓
question embedding
   ↓
vector search
   ↓
top relevant chunks
   ↓
LLM prompt
   ↓
answer + sources
```

What's happening:
The backend is responsible for combining retrieval and generation.

Why it matters:
This is the heart of RAG. If retrieval is poor, even a strong LLM may produce a weak answer.

---

### Byte 4: Health and Configuration
**Builds on:** Bytes 1–3

**In plain terms:**
The backend depends on environment configuration for things such as the database connection, CORS, and the Groq API key.

**The code:**
```text
DATABASE_URL
GROQ_API_KEY
CORS_ORIGINS
ENV
LOG_LEVEL
```

What's happening:
Configuration is injected into the backend rather than hard-coded into application logic.

Why it matters:
Secrets such as the Groq API key must remain outside source control.
