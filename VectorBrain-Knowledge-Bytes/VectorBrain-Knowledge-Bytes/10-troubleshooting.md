# Knowledge Bytes — Troubleshooting Playbook

### Byte 1: Start With the Layer
**Builds on:** Project Overview

**In plain terms:**
Do not restart everything immediately. Identify whether the failure is frontend, backend, database, document processing, AI generation, or tunneling.

**The code:**
```text
UI
 ↓
API
 ↓
DB / processing / retrieval / LLM
 ↓
ngrok
```

What's happening:
Each layer can fail independently.

Why it matters:
Layered diagnosis avoids destructive or unnecessary changes.

---

### Byte 2: Missing Database Relation
**Builds on:** Database Byte 4

**In plain terms:**
An error such as `relation "documents" does not exist` means the application is querying a table that has not been created in the current database schema.

**The code:**
```powershell
docker compose exec backend alembic upgrade head
```

What's happening:
The migration system applies the pending database schema changes.

Why it matters:
The database container can be healthy while the application's schema is still incomplete.

---

### Byte 3: Missing libxcb.so.1
**Builds on:** Document Processing Byte 3

**In plain terms:**
An error like `libxcb.so.1: cannot open shared object file` indicates that the backend image is missing a Linux shared library required by a native dependency.

**The code:**
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxcb1 \
    && rm -rf /var/lib/apt/lists/*
```

What's happening:
The package installs the missing shared library into the image.

Why it matters:
The fix belongs in the backend image, not in Vue, PostgreSQL, or ngrok.

---

### Byte 4: Frontend Vite Parse Error
**Builds on:** Frontend Byte 1

**In plain terms:**
If Vite reports `Unexpected token` in `vite.config.ts`, the configuration file contains invalid TypeScript/JavaScript syntax, often caused by duplicated or accidentally inserted configuration blocks.

**The code:**
```text
vite.config.ts
   ↓
parse error
   ↓
Vite cannot start
```

What's happening:
Vite must successfully load its configuration before the dev server can start.

Why it matters:
Fix the syntax first; changing Docker or ngrok cannot repair invalid source code.

---

### Byte 5: PowerShell Path Mistake
**Builds on:** Byte 4

**In plain terms:**
A prompt such as `PS C:\...\frontend>` is not a command. Typing it into PowerShell causes PowerShell to interpret the path as a process/command.

**The code:**
```powershell
cd "C:\Users\...\frontend"
```

What's happening:
`cd` changes the working directory correctly.

Why it matters:
Always type only the command, not the displayed PowerShell prompt.
