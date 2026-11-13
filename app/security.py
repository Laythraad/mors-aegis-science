"""Local API authentication and bounded request controls."""
from __future__ import annotations

import hmac
import json
import os
import re
import secrets
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


_attempts: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()
_sessions: dict[str, tuple[str, float]] = {}
_SESSION_TTL = 8 * 60 * 60


def issue_session(owner: str) -> str:
    token = secrets.token_urlsafe(32)
    digest = __import__('hashlib').sha256(token.encode()).hexdigest()
    now = time.monotonic()
    with _lock:
        for key, (_, expires) in list(_sessions.items()):
            if expires <= now:
                del _sessions[key]
        while len(_sessions) >= 1024:
            del _sessions[next(iter(_sessions))]
        _sessions[digest] = (owner, now + _SESSION_TTL)
    return token


def session_owner(token: str) -> str | None:
    digest = __import__('hashlib').sha256(token.encode()).hexdigest()
    with _lock:
        item = _sessions.get(digest)
        if item and item[1] > time.monotonic():
            return item[0]
        _sessions.pop(digest, None)
    return None


def revoke_session(token: str) -> None:
    digest = __import__('hashlib').sha256(token.encode()).hexdigest()
    with _lock:
        _sessions.pop(digest, None)


def configured_users() -> dict[str, str]:
    users: dict[str, str] = {}
    single = os.getenv("AEGIS_ACCESS_TOKEN", "")
    if single:
        users["local"] = single
    raw = os.getenv("AEGIS_USERS_JSON", "")
    if raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("AEGIS_USERS_JSON must be a JSON object") from exc
        if not isinstance(parsed, dict) or any(not isinstance(k, str) or not isinstance(v, str) or not k or not v for k, v in parsed.items()):
            raise RuntimeError("AEGIS_USERS_JSON must map user names to nonempty tokens")
        users.update(parsed)
    if any(not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", owner) for owner in users):
        raise RuntimeError("Owner names must use letters, digits, underscore or hyphen")
    if any(len(token) < 12 or token.startswith("REPLACE_") for token in users.values()):
        raise RuntimeError("Access tokens must be at least 12 characters and not placeholders")
    return users


def owner_for_token(token: str) -> str | None:
    matched = None
    for owner, expected in configured_users().items():
        if hmac.compare_digest(token, expected):
            matched = owner
    return matched


def require_owner(request: Request) -> str:
    owner = getattr(request.state, "owner", None)
    if owner is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return owner


def limit_request(bucket: str, key: str, maximum: int, window_seconds: int = 60) -> None:
    now = time.monotonic()
    name = f"{bucket}:{key}"
    with _lock:
        queue = _attempts[name]
        while queue and queue[0] <= now - window_seconds:
            queue.popleft()
        if len(queue) >= maximum:
            raise HTTPException(status_code=429, detail="Request limit exceeded; retry later", headers={"Retry-After": str(window_seconds)})
        queue.append(now)
