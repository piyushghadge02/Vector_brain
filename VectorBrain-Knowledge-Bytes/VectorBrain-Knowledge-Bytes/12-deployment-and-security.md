# Knowledge Bytes — Deployment and Security

### Byte 1: Environment Separation
**Builds on:** Backend Byte 4

**In plain terms:**
Environment-specific settings should be provided through environment variables or environment files rather than committed secrets.

**The code:**
```text
.env
├── GROQ_API_KEY
└── database/config values
```

What's happening:
The application reads configuration at runtime.

Why it matters:
Secrets should never be committed to GitHub.

---

### Byte 2: Public Development Tunnel
**Builds on:** ngrok Byte 1

**In plain terms:**
ngrok is suitable for temporary development access, not automatically a production deployment strategy.

**The code:**
```text
local application
      ↓
temporary tunnel
      ↓
public URL
```

What's happening:
The tunnel exposes a developer machine/service to the internet.

Why it matters:
Public exposure increases the importance of authentication, secret handling, and access controls.

---

### Byte 3: Production Boundary
**Builds on:** Byte 2

**In plain terms:**
A production deployment should run the frontend/backend/database with deliberate networking, secret management, persistence, and monitoring rather than relying on a developer's laptop and an open tunnel.

**The code:**
```text
production frontend
        ↓
production API
        ↓
managed DB / vector store
        ↓
LLM provider
```

What's happening:
The production architecture separates development conveniences from persistent hosted infrastructure.

Why it matters:
It improves reliability and reduces the risk of exposing local services unintentionally.
