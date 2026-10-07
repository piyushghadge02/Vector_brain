# Knowledge Bytes — Vue Frontend

### Byte 1: The Frontend's Responsibility
**Builds on:** Project Overview Byte 2

**In plain terms:**
The Vue.js frontend is responsible for making the document and chat workflow understandable and interactive. It manages the visible state of uploaded documents and user questions.

**The code:**
```text
App
 ├── Document Manager
 └── Chat Interface
```

What's happening:
The main application coordinates document management and querying while child components focus on their own responsibilities.

Why it matters:
Separating responsibilities prevents one large component from becoming responsible for the entire application.

---

### Byte 2: Document Management
**Builds on:** Byte 1

**In plain terms:**
The document-management part handles selecting/uploading PDFs and displaying the user's document collection.

**The code:**
```js
for (const file of files) {
  const formData = new FormData()
  formData.append('file', file)
  await api.uploadDocument(formData)
}
```

What's happening:
Each selected file is placed into multipart form data and sent to the backend upload endpoint.

Why it matters:
The frontend should treat document upload as an API operation and let the backend own processing and persistence.

---

### Byte 3: Chat Requests
**Builds on:** Byte 2

**In plain terms:**
The chat interface sends a question to the backend instead of trying to perform retrieval in the browser.

**The code:**
```js
const response = await fetch('/api/chat', {
  method: 'POST',
  body: JSON.stringify({
    question,
    allDocs: true
  })
})
```

What's happening:
The browser sends the user's question and indicates that the query should use the document collection.

Why it matters:
Keeping retrieval and generation on the backend centralizes data access, embeddings, and model calls.

---

### Byte 4: Source-Aware Answers
**Builds on:** Byte 3

**In plain terms:**
The interface is designed to show not only an answer but also information about where the answer came from.

**The code:**
```text
Answer
└── Source / citation
    ├── filename
    └── page or relevant location
```

What's happening:
Retrieved document metadata can be surfaced alongside the generated response.

Why it matters:
Source information makes a study assistant more trustworthy and easier to verify.
