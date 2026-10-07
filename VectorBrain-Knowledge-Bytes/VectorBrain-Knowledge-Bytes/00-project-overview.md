# Knowledge Bytes — Project Overview

### Byte 1: What VectorBrain Is
**Builds on:** None — starting point

**In plain terms:**
VectorBrain is a "second brain" for studying and research. The user uploads multiple PDFs and then asks questions across those documents using retrieval-augmented generation (RAG).

**The code:**
```text
PDFs → document processing → stored content/chunks → embeddings
    → PostgreSQL/pgvector search → relevant context → Groq answer
```

What's happening:
The system turns uploaded documents into searchable knowledge, retrieves the most relevant pieces for a question, and uses those pieces as context for an AI-generated answer.

Why it matters:
Without this pipeline, the application would only be a file uploader or a generic chatbot rather than a document-grounded research assistant.

---

### Byte 2: The Main Technology Roles
**Builds on:** Byte 1

**In plain terms:**
Each technology has a focused job: Vue manages the interface, FastAPI exposes backend operations, PostgreSQL stores application data, pgvector enables similarity search, Docling processes PDFs, and Groq generates answers.

**The code:**
```text
Vue.js 3       → UI
FastAPI        → API/backend
PostgreSQL     → persistent data
pgvector       → vector similarity search
Docling        → document extraction
Groq API       → answer generation
```

What's happening:
The components form a pipeline rather than independent features.

Why it matters:
Knowing these boundaries makes debugging much easier: a UI problem is different from a database, document-processing, or LLM problem.

---

### Byte 3: Multi-Document RAG
**Builds on:** Bytes 1–2

**In plain terms:**
The important distinction is that questions are answered from the user's uploaded documents rather than from the model alone. Retrieval selects useful document content before generation.

**The code:**
```text
Question
   ↓
Vector search
   ↓
Relevant document chunks
   ↓
Prompt/context
   ↓
LLM
   ↓
Answer + sources
```

What's happening:
The question is converted into a representation that can be compared with stored document representations.

Why it matters:
This is the core mechanism that makes answers document-grounded.

---

### Byte 4: Project Definition of Done
**Builds on:** Bytes 1–3

**In plain terms:**
The project is successful when multiple PDFs can be uploaded, searched together, and used to produce useful answers with source information.

**The code:**
```text
Multiple PDFs
→ Query all documents
→ Retrieve relevant content
→ Generate answer
→ Show source/citation information
```

What's happening:
The definition describes the complete user journey rather than one individual technical component.

Why it matters:
It gives every implementation decision a target: improve the end-to-end research workflow.
