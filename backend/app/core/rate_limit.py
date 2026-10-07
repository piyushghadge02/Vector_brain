"""Rate limiting (slowapi).

The chat endpoint calls a paid API per request, so it gets a per-IP limit.
Exceeding it returns 429 with the standard error envelope (see main.py).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
