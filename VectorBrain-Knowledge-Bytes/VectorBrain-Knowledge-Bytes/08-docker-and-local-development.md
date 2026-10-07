# Knowledge Bytes — Docker and Local Development

### Byte 1: Why Docker Is Used
**Builds on:** Project Overview

**In plain terms:**
Docker packages the backend, frontend, and database into reproducible services.

**The code:**
```text
vectorbrain
├── backend
├── frontend
└── db
```

What's happening:
Docker Compose coordinates the multi-container application.

Why it matters:
The project can be started with a consistent environment instead of manually installing every service.

---

### Byte 2: Service Ports
**Builds on:** Byte 1

**In plain terms:**
The development stack exposes separate ports for the frontend, backend, and database.

**The code:**
```text
frontend → 5173/5176 depending on current dev configuration
backend  → 8000
database → 5432
```

What's happening:
The exact frontend port depends on the active Vite configuration/environment at the time.

Why it matters:
A tunnel must target the port where the frontend is actually listening.

---

### Byte 3: Health Is Not the Same as Readiness
**Builds on:** Byte 2

**In plain terms:**
A container being "Up" or "healthy" does not prove that every application feature is working.

**The code:**
```text
container running
    ≠
database migrated
    ≠
PDF processing working
    ≠
Groq configured
```

What's happening:
Different layers can fail independently.

Why it matters:
Debug the failing layer rather than repeatedly restarting every container.

---

### Byte 4: Rebuild After Dockerfile Changes
**Builds on:** Byte 3

**In plain terms:**
If a system package is added to the backend Dockerfile, the image must be rebuilt before the running container gets that package.

**The code:**
```powershell
docker compose up -d --build backend
```

What's happening:
Docker rebuilds the backend image and recreates/runs the service with the new image.

Why it matters:
Restarting an old container does not install packages that were never present in its image.
