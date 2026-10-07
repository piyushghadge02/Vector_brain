# Knowledge Bytes — PostgreSQL + pgvector

### Byte 1: Why PostgreSQL Is Used
**Builds on:** Project Overview

**In plain terms:**
PostgreSQL provides persistent storage for application data and document information.

**The code:**
```text
Application
    ↓
PostgreSQL
    ├── documents
    ├── chunks/content
    └── vector data
```

What's happening:
The database keeps the system's knowledge available after the application restarts.

Why it matters:
Without persistent storage, uploaded knowledge would disappear with the running process.

---

### Byte 2: What pgvector Adds
**Builds on:** Byte 1

**In plain terms:**
pgvector adds vector storage and similarity-search operations to PostgreSQL.

**The code:**
```sql
CREATE EXTENSION vector;
```

What's happening:
The PostgreSQL extension enables vector columns and vector distance operators.

Why it matters:
Vector search is the retrieval mechanism that connects a natural-language question to semantically related document content.

---

### Byte 3: Embedding Search
**Builds on:** Byte 2

**In plain terms:**
An embedding represents text as a numeric vector. Similar meanings tend to produce vectors that are close under an appropriate similarity/distance measure.

**The code:**
```sql
SELECT content, filename
FROM documents
ORDER BY embedding <=> :query_vector
LIMIT 5;
```

What's happening:
The query vector is compared against stored vectors and the closest results are selected.

Why it matters:
These top results become the evidence supplied to the answer-generation stage.

---

### Byte 4: Data and Migration Safety
**Builds on:** Bytes 1–3

**In plain terms:**
The database schema must exist before API queries can work. Schema changes should be managed through migrations rather than manually changing production tables.

**The code:**
```text
migration
   ↓
database schema
   ↓
application queries
```

What's happening:
During development, an unrun migration can cause errors such as a missing `documents` relation.

Why it matters:
A healthy database container does not automatically mean the application schema has been created.
