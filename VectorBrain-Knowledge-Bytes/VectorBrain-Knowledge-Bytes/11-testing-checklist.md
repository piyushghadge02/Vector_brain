# Knowledge Bytes — Testing Checklist

### Byte 1: Infrastructure Check
**Builds on:** Troubleshooting Byte 1

**In plain terms:**
Before testing RAG, verify that Docker services are running and reachable.

**The code:**
```powershell
docker ps
docker compose ps
```

What's happening:
These commands show the state of the running containers/services.

Why it matters:
There is little value in debugging application behavior while the required service is stopped.

---

### Byte 2: Backend Check
**Builds on:** Byte 1

**In plain terms:**
Confirm the FastAPI service is healthy before testing uploads or chat.

**The code:**
```text
backend → healthy
port 8000 → reachable
```

What's happening:
The backend is the gateway to the database and processing pipeline.

Why it matters:
A frontend "network error" may simply mean the API is unavailable.

---

### Byte 3: Document Ingestion Test
**Builds on:** Byte 2

**In plain terms:**
Upload a small PDF and verify that its state moves from upload/processing to successfully processed.

**The code:**
```text
PDF
→ processing
→ processed
```

What's happening:
This validates storage, Docling, chunking/embedding, and database persistence as a group.

Why it matters:
Do this before testing question answering.

---

### Byte 4: RAG Test
**Builds on:** Byte 3

**In plain terms:**
Ask a question whose answer is clearly present in the uploaded document.

**The code:**
```text
Question
→ retrieval
→ grounded answer
→ source
```

What's happening:
A known-answer question makes retrieval failures easier to identify.

Why it matters:
It tests the actual purpose of the system instead of only checking that the UI loads.
