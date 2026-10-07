# Knowledge Bytes — PDF Processing with Docling

### Byte 1: Why Document Processing Exists
**Builds on:** Project Overview

**In plain terms:**
A PDF is not automatically useful to a retrieval system. Its content must be extracted and transformed into searchable text/structure first.

**The code:**
```text
PDF
 ↓
Docling
 ↓
structured document content
 ↓
chunks
 ↓
embeddings
```

What's happening:
Docling is the document-processing layer in the documented VectorBrain stack.

Why it matters:
If extraction fails, there is no reliable text to embed or retrieve.

---

### Byte 2: Processing Is a Pipeline
**Builds on:** Byte 1

**In plain terms:**
Document ingestion is more than simply saving the uploaded PDF. Processing can involve extraction, chunking, embedding, and persistence.

**The code:**
```text
upload
→ extract
→ normalize/chunk
→ embed
→ store
```

What's happening:
Each stage prepares data for the next stage.

Why it matters:
A document can be successfully uploaded while still failing during processing.

---

### Byte 3: Native Dependency Failures
**Builds on:** Byte 2

**In plain terms:**
Document-processing libraries may depend on Linux shared libraries that are not present in a minimal Docker image.

**The code:**
```text
Python package
   ↓
native dependency
   ↓
Linux shared library
```

What's happening:
A missing library such as `libxcb.so.1` can cause PDF processing to fail even though Python and Docker themselves are running correctly.

Why it matters:
When the backend is healthy but every PDF fails during processing, inspect backend logs for native-library errors before changing the frontend.

---

### Byte 4: Model Downloads
**Builds on:** Byte 2

**In plain terms:**
Some document-processing components may download model assets on first use. Network access and container permissions therefore affect first-run processing.

**The code:**
```text
first document
   ↓
load required model
   ↓
cache/download
   ↓
process document
```

What's happening:
A first run may be slower than later runs.

Why it matters:
A successful model download is evidence that the container can reach the required external resources.
