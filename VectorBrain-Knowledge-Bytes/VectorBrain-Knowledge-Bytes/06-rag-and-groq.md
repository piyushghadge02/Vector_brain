# Knowledge Bytes — RAG + Groq

### Byte 1: What RAG Means
**Builds on:** Embeddings and Retrieval Byte 3

**In plain terms:**
RAG means Retrieval-Augmented Generation. The system retrieves relevant information first and then asks the language model to answer using that information.

**The code:**
```text
Question
 → Retrieve evidence
 → Add evidence to prompt
 → Generate answer
```

What's happening:
The model is given project-specific context rather than relying only on its pretrained knowledge.

Why it matters:
This is what makes the assistant useful for the user's uploaded study material.

---

### Byte 2: Building the Context
**Builds on:** Byte 1

**In plain terms:**
The retrieved chunks become context for the generation request.

**The code:**
```text
retrieved chunks
      ↓
context
      +
question
      ↓
generation prompt
```

What's happening:
The backend combines the user's intent with evidence from the vector search.

Why it matters:
The quality and relevance of the context directly affect the answer.

---

### Byte 3: Groq as the Generation Layer
**Builds on:** Byte 2

**In plain terms:**
The documented architecture uses the Groq API for answer generation after retrieval.

**The code:**
```text
RAG context
   ↓
Groq API
   ↓
generated answer
```

What's happening:
Groq is the model-serving layer, not the document database.

Why it matters:
This separation means retrieval can remain grounded in PostgreSQL while generation is handled by the external LLM service.

---

### Byte 4: Missing API Key
**Builds on:** Byte 3

**In plain terms:**
A running backend can still be unable to generate AI answers if the Groq API key is missing or unavailable inside the container.

**The code:**
```text
backend environment
   ↓
GROQ_API_KEY
   ↓
Groq request
```

What's happening:
The key should be supplied through environment configuration.

Why it matters:
Never commit the real secret to GitHub or paste it into public logs.
