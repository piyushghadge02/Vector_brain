# Knowledge Bytes — ngrok Public Access

### Byte 1: What ngrok Does
**Builds on:** Docker and Local Development

**In plain terms:**
ngrok exposes a local HTTP service through a public HTTPS URL so another device or external service can reach the development frontend.

**The code:**
```text
Internet
   ↓
ngrok public URL
   ↓
localhost frontend
```

What's happening:
ngrok creates a tunnel to a local port.

Why it matters:
It allows the locally running application to be tested through a public address.

---

### Byte 2: Reserved Domain Conflicts
**Builds on:** Byte 1

**In plain terms:**
A reserved ngrok domain can only be served by an active tunnel session unless configured for pooling. If another session owns it, a new tunnel gets `ERR_NGROK_334`.

**The code:**
```text
ERR_NGROK_334
→ endpoint already online
→ stop existing ngrok process/session
```

What's happening:
The problem is tunnel ownership, not Docker.

Why it matters:
Repeatedly restarting Docker will not fix a domain that is already claimed by another ngrok session.

---

### Byte 3: Clean ngrok Restart
**Builds on:** Byte 2

**In plain terms:**
On Windows, stop local ngrok processes before starting the reserved domain again.

**The code:**
```powershell
Get-Process ngrok -ErrorAction SilentlyContinue
Stop-Process -Name ngrok -Force
ngrok http --domain=YOUR_DOMAIN YOUR_PORT
```

What's happening:
The first command checks for a process, the second terminates it, and the last command creates a fresh tunnel.

Why it matters:
This avoids local duplicate sessions.

---

### Byte 4: Keep the Tunnel Window Open
**Builds on:** Byte 3

**In plain terms:**
The terminal running ngrok is part of the active tunnel. Closing it or pressing Ctrl+C stops the tunnel.

**The code:**
```text
PowerShell window
      ↓
running ngrok process
      ↓
public URL
```

What's happening:
The public URL depends on the active tunnel process.

Why it matters:
A public link can stop working even when Docker and the frontend are still healthy.
