# Knowledge Bytes — Embeddings and Retrieval

### Byte 1: Turning Text into Vectors
**Builds on:** Document Processing Byte 2

**In plain terms:**
Embeddings convert text into a numeric representation that can be compared with another piece of text.

**The code:**
```text
text
  ↓
embedding model
  ↓
[0.12, -0.04, 0.81, ...]
```

What's happening:
The vector captures semantic characteristics rather than storing the text as a normal keyword index.

Why it matters:
This enables meaning-based retrieval.

---

### Byte 2: Query Embedding
**Builds on:** Byte 1

**In plain terms:**
The user's question must be represented in the same vector space as the stored document chunks.

**The code:**
```text
user question
     ↓
same embedding space
     ↓
query vector
```

What's happening:
Using compatible representations allows the query to be compared against stored document vectors.

Why it matters:
A mismatch between indexing and query embeddings can make retrieval ineffective.

---

### Byte 3: Top-K Retrieval
**Builds on:** Byte 2

**In plain terms:**
The system usually retrieves a small number of the most relevant chunks rather than sending an entire document to the LLM.

**The code:**
```text
query vector
   ↓
similarity search
   ↓
top K chunks
```

What's happening:
Only the strongest candidates are selected as context.

Why it matters:
This controls prompt size and focuses the model on evidence relevant to the question.

---

### Byte 4: Retrieval Quality
**Builds on:** Byte 3

**In plain terms:**
RAG quality depends heavily on chunking and retrieval quality. If the right information is never retrieved, the generation step cannot reliably use it.

**The code:**
```text
good retrieval → useful context → better answer
bad retrieval  → wrong/missing context → weak answer
```

What's happening:
Generation cannot compensate for completely missing evidence.

Why it matters:
When answers are wrong, inspect retrieval before assuming the LLM is the only problem.
