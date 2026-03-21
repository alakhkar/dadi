"""
analytics.py — Fire-and-forget event logging to Supabase analytics_events table.

All public functions schedule a background task and return immediately.
Exceptions are swallowed so analytics failures NEVER affect the chat.

Usage:
    import analytics
    analytics.init(SUPABASE_URL, SUPABASE_KEY)   # call once at startup
    await analytics.log_session_start(...)        # call from async handlers
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import httpx

from starters import STARTER_SETS

# ── Module state ─────────────────────────────────────────────────────────────

_endpoint: str = ""
_headers: dict  = {}
_enabled: bool  = False

# Pre-build a {message_text: label} lookup from all starter sets
_STARTER_LOOKUP: dict[str, str] = {
    message: label
    for starter_set in STARTER_SETS
    for label, message in starter_set
}


# ── Initialisation ────────────────────────────────────────────────────────────

def init(supabase_url: str, supabase_key: str) -> None:
    """Call once at app startup before any events fire."""
    global _endpoint, _headers, _enabled
    if not supabase_url or not supabase_key:
        print("[Analytics] Missing Supabase config — analytics disabled.")
        return
    _endpoint = f"{supabase_url}/rest/v1/analytics_events"
    _headers = {
        "apikey":        supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type":  "application/json",
        "Prefer":        "return=minimal",
    }
    _enabled = True
    print("[Analytics] Initialised ✓")


# ── Core internals ─────────────────────────────────────────────────────────────

async def _log(
    event_name: str,
    session_id: str | None,
    user_email: str | None,
    user_type: str,
    properties: dict[str, Any] | None = None,
) -> None:
    if not _enabled:
        return
    payload = {
        "event_name": event_name,
        "session_id": session_id,
        "user_email": user_email,
        "user_type":  user_type,
        "properties": properties or {},
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(_endpoint, headers=_headers, json=payload)
    except Exception as e:
        print(f"[Analytics] Log failed ({event_name}): {e}")


def _fire(coro) -> None:
    """Schedule coro as a fire-and-forget background task."""
    try:
        asyncio.create_task(coro)
    except RuntimeError:
        # No running event loop (e.g. called from sync context)
        asyncio.ensure_future(coro)


# ── Public event helpers ──────────────────────────────────────────────────────

async def log_session_start(
    session_id: str,
    user_email: str | None,
    user_type: str,
    memory_count: int,
) -> None:
    _fire(_log(
        "session_start", session_id, user_email, user_type,
        {"memory_count": memory_count, "is_guest": user_type == "guest"},
    ))


async def log_session_end(
    session_id: str,
    user_email: str | None,
    user_type: str,
    message_count: int,
    started_at: datetime | None,
) -> None:
    duration = 0
    if started_at:
        duration = int((datetime.now(timezone.utc) - started_at).total_seconds())
    _fire(_log(
        "session_end", session_id, user_email, user_type,
        {"message_count": message_count, "duration_seconds": duration},
    ))


async def log_message(
    session_id: str,
    user_email: str | None,
    user_type: str,
    message_index: int,
    user_text: str,
    rag_used: bool,
    rag_doc_count: int,
) -> None:
    _fire(_log(
        "message_sent", session_id, user_email, user_type,
        {
            "message_index": message_index,
            "rag_used":      rag_used,
            "rag_doc_count": rag_doc_count,
            "char_count":    len(user_text),
        },
    ))
    # Detect starter prompt on first message
    if message_index == 0:
        label = _STARTER_LOOKUP.get(user_text.strip())
        if label:
            _fire(_log(
                "starter_used", session_id, user_email, user_type,
                {"starter_label": label},
            ))


async def log_memory_extracted(
    session_id: str,
    user_email: str | None,
    user_type: str,
    facts_count: int,
    trigger: str,  # 'periodic' | 'session_end'
) -> None:
    _fire(_log(
        "memory_extracted", session_id, user_email, user_type,
        {"facts_count": facts_count, "trigger": trigger},
    ))


async def log_otp_requested(email: str) -> None:
    domain = email.split("@")[-1] if "@" in email else ""
    _fire(_log("otp_requested", None, None, "registered", {"email_domain": domain}))


async def log_otp_verified(email: str) -> None:
    domain = email.split("@")[-1] if "@" in email else ""
    _fire(_log("otp_verified", None, None, "registered", {"email_domain": domain}))


async def log_otp_failed() -> None:
    _fire(_log("otp_failed", None, None, "registered", {}))


async def log_guest_login() -> None:
    _fire(_log("guest_login", None, None, "guest", {}))
