import chainlit as cl
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
import os
import json
import random
import string
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

import httpx
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.documents import Document
from prompt import DADI_SYSTEM_PROMPT
from starters import STARTER_SETS
import analytics

# ─────────────────────────────────────────────
# 1. ENV / SECRETS
# ─────────────────────────────────────────────
GROQ_API_KEY          = os.environ["GROQ_API_KEY"]
SUPABASE_URL          = os.environ["SUPABASE_URL"]
SUPABASE_KEY          = os.environ["SUPABASE_KEY"]
DATABASE_URL          = os.environ["DATABASE_URL"]
RESEND_API_KEY        = os.environ.get("RESEND_API_KEY")
EMAIL_FROM            = os.environ.get("EMAIL_FROM", "Dadi <onboarding@resend.dev>")
ANALYTICS_ADMIN_TOKEN    = os.environ.get("ANALYTICS_ADMIN_TOKEN", "")
ANALYTICS_ADMIN_EMAIL    = os.environ.get("ANALYTICS_ADMIN_EMAIL", "")
ANALYTICS_ADMIN_PASSWORD = os.environ.get("ANALYTICS_ADMIN_PASSWORD", "")
LLM_PROVIDER          = os.environ.get("LLM_PROVIDER", "groq").lower()  # "groq" or "deepseek"

analytics.init(SUPABASE_URL, SUPABASE_KEY)

# ─────────────────────────────────────────────
# 2. CHAINLIT DATA LAYER
# ─────────────────────────────────────────────
@cl.data_layer
def get_data_layer():
    return SQLAlchemyDataLayer(conninfo=DATABASE_URL)

# ─────────────────────────────────────────────
# 3. EMBEDDINGS + LLM
# ─────────────────────────────────────────────
print("[Startup] Loading embeddings model...")
EMBEDDINGS = HuggingFaceEndpointEmbeddings(
    model="sentence-transformers/all-MiniLM-L6-v2",
    huggingfacehub_api_token=os.environ.get("HUGGINGFACEHUB_API_TOKEN"),
)

if LLM_PROVIDER == "deepseek":
    from langchain_openai import ChatOpenAI
    LLM = ChatOpenAI(
        model="deepseek-ai/DeepSeek-V3.2:novita",
        api_key=os.environ.get("HUGGINGFACEHUB_API_TOKEN"),
        base_url="https://router.huggingface.co/v1",
        temperature=0.8,
        streaming=True,
    )
    print("[LLM] Using DeepSeek-V3.2 via HuggingFace router (novita)")
else:
    LLM = ChatGroq(
        model="openai/gpt-oss-120b",
        api_key=GROQ_API_KEY,
        temperature=0.8,
        streaming=True,
    )
    print("[LLM] Using Groq (gpt-oss-120b)")

# ─────────────────────────────────────────────
# 4. SUPABASE REST HELPERS
# ─────────────────────────────────────────────
SUPA_HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
}

def _has_knowledge() -> bool:
    try:
        r = httpx.get(f"{SUPABASE_URL}/rest/v1/dadi_knowledge?select=content&limit=1", headers=SUPA_HEADERS, timeout=10)
        return bool(r.json())
    except Exception as e:
        print(f"[RAG] Table check failed: {e}")
        return False

def _upload_chunks(chunks: list) -> bool:
    url = f"{SUPABASE_URL}/rest/v1/dadi_knowledge"
    headers = {**SUPA_HEADERS, "Prefer": "return=minimal"}
    for i, chunk in enumerate(chunks):
        embedding = EMBEDDINGS.embed_query(chunk.page_content)
        r = httpx.post(url, headers=headers, json={"content": chunk.page_content, "metadata": chunk.metadata, "embedding": embedding}, timeout=30)
        if r.status_code not in (200, 201):
            print(f"[RAG] Upload failed for chunk {i}: {r.text}")
            return False
        if i % 5 == 0:
            print(f"[RAG] Uploaded {i+1}/{len(chunks)} chunks...")
    return True

async def _retrieve(query: str, k: int = 3) -> list[Document]:
    try:
        embedding = await EMBEDDINGS.aembed_query(query)
    except Exception as e:
        print(f"[RAG] Embedding failed: {e}")
        return []
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/match_dadi_knowledge",
            headers=SUPA_HEADERS,
            json={"query_embedding": embedding, "match_count": k, "filter": {}},
            timeout=15,
        )
    if r.status_code != 200:
        print(f"[RAG] Retrieval failed: {r.text}")
        return []
    return [Document(page_content=row["content"], metadata=row.get("metadata", {})) for row in r.json()]

# ── Cricket (CricAPI) ─────────────────────────────────────────────────────────

_CRICKET_CACHE: dict = {"context": "", "ts": 0.0}
_CRICKET_TTL   = 120  # seconds
_CRICKET_KEYWORDS = {
    "cricket", "ipl", "match", "score", "wicket", "batting", "bowling",
    "runs", "t20", "test", "odi", "innings", "over", "boundary", "six",
    "rcb", "csk", "mi", "kkr", "srh", "dc", "pbks", "rr", "gt", "lsg",
    "virat", "rohit", "dhoni", "bumrah", "player of the match",
    "india won", "india lost", "team india", "points table", "standings",
}

def _is_cricket_query(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in _CRICKET_KEYWORDS)

async def _get_cricket_context() -> str:
    """Fetch live matches + IPL points table from CricAPI. Cached for 120s."""
    import time
    cricapi_key = os.environ.get("CRICAPI_KEY", "")
    if not cricapi_key:
        return ""
    now = time.time()
    if _CRICKET_CACHE["context"] and now - _CRICKET_CACHE["ts"] < _CRICKET_TTL:
        return _CRICKET_CACHE["context"]
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            matches_resp, series_resp = await asyncio.gather(
                client.get(
                    "https://api.cricapi.com/v1/currentMatches",
                    params={"apikey": cricapi_key, "offset": 0},
                ),
                client.get(
                    "https://api.cricapi.com/v1/series",
                    params={"apikey": cricapi_key, "offset": 0, "search": "IPL"},
                ),
                return_exceptions=True,
            )

        lines = []

        # ── Current / live matches ─────────────────────────────────────────
        if not isinstance(matches_resp, Exception) and matches_resp.status_code == 200:
            mdata = matches_resp.json()
            if mdata.get("status") == "success":
                matches = mdata.get("data", [])
                # Prioritise IPL, fall back to all matches
                ipl = [m for m in matches if "ipl" in m.get("name", "").lower()]
                display = ipl if ipl else matches[:6]
                if display:
                    lines.append("Current Cricket Matches:")
                    for m in display:
                        name   = m.get("name", "")
                        status = m.get("status", "")
                        scores = m.get("score", [])
                        score_parts = [
                            f"{s.get('inning','').split(',')[0]}: "
                            f"{s.get('r','')} / {s.get('w','')} "
                            f"({s.get('o','')} ov)"
                            for s in scores
                        ]
                        lines.append(f"• {name}")
                        if score_parts:
                            lines.append("  " + " | ".join(score_parts))
                        if status:
                            lines.append(f"  {status}")

        # ── IPL points table ───────────────────────────────────────────────
        ipl_series_id = None
        if not isinstance(series_resp, Exception) and series_resp.status_code == 200:
            sdata = series_resp.json()
            if sdata.get("status") == "success":
                for s in sdata.get("data", []):
                    if "ipl" in s.get("name", "").lower():
                        ipl_series_id = s.get("id")
                        break

        if ipl_series_id:
            async with httpx.AsyncClient(timeout=10.0) as client:
                pts_resp = await client.get(
                    "https://api.cricapi.com/v1/series_points",
                    params={"apikey": cricapi_key, "id": ipl_series_id},
                )
            if pts_resp.status_code == 200:
                pdata = pts_resp.json()
                if pdata.get("status") == "success":
                    table = pdata.get("data", [])
                    if table:
                        lines.append("\nIPL Points Table:")
                        for row in table:
                            team = row.get("teamName") or row.get("team", "")
                            p    = row.get("p") or row.get("matchesPlayed", "")
                            w    = row.get("w") or row.get("win", "")
                            l    = row.get("l") or row.get("loss", "")
                            pts  = row.get("pts") or row.get("points", "")
                            lines.append(f"  {team}: P{p} W{w} L{l} Pts{pts}")

        if not lines:
            return ""

        context = "\n".join(lines)
        _CRICKET_CACHE["context"] = context
        _CRICKET_CACHE["ts"]      = now
        print(f"[Cricket] Fetched {len(lines)} lines of cricket data")
        return context
    except Exception as e:
        print(f"[Cricket] CricAPI failed: {e}")
        return ""


async def _web_search(query: str, max_results: int = 3) -> list[dict]:
    """DuckDuckGo search, returns list of {title, body, href}. Never raises."""
    try:
        from duckduckgo_search import DDGS
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            lambda: list(DDGS().text(query, max_results=max_results))
        )
        return results
    except Exception as e:
        print(f"[Search] DuckDuckGo failed: {e}")
        return []

# ─────────────────────────────────────────────
# 5. OTP HELPERS
# ─────────────────────────────────────────────
def _generate_otp() -> str:
    return "".join(random.choices(string.digits, k=6))

async def _save_otp(email: str, code: str) -> bool:
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{SUPABASE_URL}/rest/v1/otp_codes",
            headers={**SUPA_HEADERS, "Prefer": "return=minimal"},
            json={"email": email, "code": code, "expires_at": expires_at},
            timeout=10,
        )
    return r.status_code in (200, 201)

def _verify_otp_sync(email: str, code: str) -> bool:
    """Synchronous OTP check — safe to call from @cl.password_auth_callback."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        with httpx.Client() as client:
            r = client.get(
                f"{SUPABASE_URL}/rest/v1/otp_codes",
                params={
                    "email": f"eq.{email}",
                    "code": f"eq.{code}",
                    "used": "eq.false",
                    "expires_at": f"gt.{now}",
                    "select": "id",
                    "limit": "1",
                },
                headers=SUPA_HEADERS,
                timeout=10,
            )
            rows = r.json() if r.status_code == 200 else []
            if not rows:
                return False
            client.patch(
                f"{SUPABASE_URL}/rest/v1/otp_codes?id=eq.{rows[0]['id']}",
                headers={**SUPA_HEADERS, "Prefer": "return=minimal"},
                json={"used": True},
                timeout=10,
            )
        return True
    except Exception as e:
        print(f"[OTP] Verify error: {e}")
        return False

async def _send_otp_email(email: str, code: str) -> bool:
    if not RESEND_API_KEY:
        print(f"[OTP] No RESEND_API_KEY — code for {email}: {code}")
        return True
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
            json={
                "from": EMAIL_FROM,
                "to": [email],
                "subject": "Your Dadi verification code",
                "text": f"Your Dadi login code is: {code}\n\nThis code expires in 10 minutes.\n\nIf you didn't request this, ignore this email.",
            },
            timeout=15,
        )
    if r.status_code != 200:
        print(f"[OTP] Resend error: {r.text}")
        return False
    return True

# ─────────────────────────────────────────────
# 6. MEMORY HELPERS
# ─────────────────────────────────────────────
async def _get_memories(email: str) -> list[str]:
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{SUPABASE_URL}/rest/v1/user_memories?user_email=eq.{email}&select=memory&order=created_at.desc&limit=20",
                headers=SUPA_HEADERS,
                timeout=10,
            )
        if r.status_code == 200:
            return [row["memory"] for row in r.json()]
    except Exception as e:
        print(f"[Memory] Load failed: {e}")
    return []

async def _save_memory(email: str, memory: str):
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{SUPABASE_URL}/rest/v1/user_memories",
                headers={**SUPA_HEADERS, "Prefer": "return=minimal"},
                json={"user_email": email, "memory": memory},
                timeout=10,
            )
    except Exception as e:
        print(f"[Memory] Save error: {e}")

async def _extract_and_save_memories(email: str, messages: list) -> int:
    """Returns number of facts saved."""
    if len(messages) < 4:
        return 0
    convo = "\n".join(
        f"{'User' if m['role'] == 'user' else 'Dadi'}: {m['content'][:300]}"
        for m in messages[-10:]
    )
    prompt = (
        "From this conversation, extract 1-3 short facts about the USER that are worth "
        "remembering for future conversations (name, city, job, family situation, recurring problems, preferences).\n"
        "Only include facts clearly stated by the user. "
        "Return ONLY a JSON array of strings. If nothing worth saving, return [].\n"
        'Example: ["Name is Priya", "Lives in Pune", "Has board exams next month"]\n\n'
        f"Conversation:\n{convo}"
    )
    saved = 0
    try:
        response = await LLM.ainvoke([HumanMessage(content=prompt)])
        text = response.content.strip()
        if text.startswith("```"):
            text = text.split("```")[1].lstrip("json").strip()
        facts = json.loads(text)
        for fact in facts[:3]:
            if isinstance(fact, str) and len(fact) > 5:
                await _save_memory(email, fact)
                print(f"[Memory] Saved for {email}: {fact}")
                saved += 1
    except Exception as e:
        print(f"[Memory] Extraction failed: {e}")
    return saved

# ─────────────────────────────────────────────
# 6. RAG — ENSURE PDF UPLOADED ON STARTUP
# ─────────────────────────────────────────────
def ensure_knowledge_uploaded():
    try:
        if _has_knowledge():
            print("[RAG] Knowledge already in Supabase ✓")
            return
        pdf_path = "dadi_knowledge.pdf"
        if not os.path.exists(pdf_path):
            print("[RAG] No PDF found — RAG disabled.")
            return
        print("[RAG] Uploading PDF to Supabase...")
        docs = PyPDFLoader(pdf_path).load()
        chunks = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200).split_documents(docs)
        if _upload_chunks(chunks):
            print(f"[RAG] Uploaded {len(chunks)} chunks ✓")
    except Exception as e:
        print(f"[RAG] Startup error: {e}")

print("[Startup] Building Dadi's brain...")
ensure_knowledge_uploaded()

print("[Startup] Pre-warming embedding model...")
try:
    EMBEDDINGS.embed_query("warmup")
    print("[Startup] Embedding model warmed up ✓")
except Exception as e:
    print(f"[Startup] Embedding warmup failed (non-fatal): {e}")

# ─────────────────────────────────────────────
# 7. OTP REST ENDPOINT
# ─────────────────────────────────────────────
try:
    import asyncio as _asyncio
    from chainlit.server import app as _cl_app
    import hmac as _hmac
    from fastapi import Request
    from fastapi.responses import JSONResponse, HTMLResponse
    from dashboard import build_dashboard_html

    @_cl_app.post("/auth/request-otp")
    async def auth_request_otp(request: Request):
        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid request"}, status_code=400)
        email = data.get("email", "").strip().lower()
        if not email or "@" not in email or "." not in email.split("@")[-1]:
            return JSONResponse({"error": "Invalid email address"}, status_code=400)
        code = _generate_otp()
        if not await _save_otp(email, code):
            return JSONResponse({"error": "Could not save code, please try again"}, status_code=500)
        if not await _send_otp_email(email, code):
            return JSONResponse({"error": "Could not send email, please check the address"}, status_code=500)
        _asyncio.create_task(analytics.log_otp_requested(email))
        return JSONResponse({"ok": True})

    @_cl_app.post("/auth/analytics-data")
    async def analytics_data(request: Request):
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid request"}, status_code=400)
        provided = body.get("token", "")
        if not ANALYTICS_ADMIN_TOKEN or provided != ANALYTICS_ADMIN_TOKEN:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

        views = [
            "v_kpi_summary", "v_dau", "v_user_type_ratio", "v_rag_usage",
            "v_top_starters", "v_otp_funnel", "v_memory_extractions", "v_session_stats",
        ]
        async with httpx.AsyncClient(timeout=15.0) as client:
            view_responses, audit_response = await _asyncio.gather(
                _asyncio.gather(*[
                    client.get(f"{SUPABASE_URL}/rest/v1/{v}?select=*", headers=SUPA_HEADERS)
                    for v in views
                ], return_exceptions=True),
                client.get(
                    f"{SUPABASE_URL}/rest/v1/analytics_events"
                    "?event_name=eq.message_sent&order=created_at.desc&limit=500",
                    headers=SUPA_HEADERS,
                ),
            )

        data = {}
        for view, resp in zip(views, view_responses):
            if isinstance(resp, Exception):
                data[view] = []
            elif resp.status_code == 200:
                data[view] = resp.json()
            else:
                data[view] = []

        data["message_audit"] = audit_response.json() if audit_response.status_code == 200 else []

        return JSONResponse(data)

    _ANALYTICS_LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dadi AI — Analytics Login</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600&family=Inter:wght@400;500&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Inter', sans-serif; background: #FDF6F0; color: #2d1a10;
         display: flex; align-items: center; justify-content: center; min-height: 100vh; }
  .card { background: #fff; border: 1px solid #f0d9c8; border-radius: 16px;
          padding: 2.5rem 2rem; width: 100%; max-width: 360px;
          box-shadow: 0 4px 20px rgba(139,26,26,.08); text-align: center; }
  h1 { font-family: 'Playfair Display', serif; color: #8B1A1A; font-size: 1.5rem; margin-bottom: 0.4rem; }
  .sub { color: #9e7a5a; font-size: 0.82rem; margin-bottom: 2rem; }
  .field { margin-bottom: 1rem; }
  label { display: block; text-align: left; font-size: 0.8rem; color: #9e7a5a;
          text-transform: uppercase; letter-spacing: .05em; margin-bottom: 0.4rem; }
  input[type=email], input[type=password] {
    width: 100%; padding: 0.65rem 0.9rem; border: 1px solid #f0d9c8;
    border-radius: 8px; font-size: 0.95rem; outline: none; transition: border-color .2s; }
  input[type=email]:focus, input[type=password]:focus { border-color: #8B1A1A; }
  button { margin-top: 0.5rem; width: 100%; padding: 0.7rem; background: #8B1A1A;
           color: #fff; border: none; border-radius: 8px; font-size: 0.95rem;
           font-weight: 500; cursor: pointer; transition: background .2s; }
  button:hover { background: #6e1414; }
  .error { color: #c0392b; font-size: 0.82rem; margin-top: 0.75rem; }
</style>
</head>
<body>
<div class="card">
  <h1>Dadi AI</h1>
  <p class="sub">Analytics — admin access only</p>
  <form method="POST" action="/auth/analytics">
    <div class="field">
      <label for="email">Email</label>
      <input type="email" id="email" name="email" placeholder="admin@example.com" autofocus required>
    </div>
    <div class="field">
      <label for="password">Password</label>
      <input type="password" id="password" name="password" placeholder="••••••••" required>
    </div>
    <button type="submit">Sign in</button>
    {error_html}
  </form>
</div>
</body>
</html>"""

    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import HTMLResponse as _HTMLResponse

    def _check_admin_credentials(email: str, password: str) -> bool:
        if not ANALYTICS_ADMIN_EMAIL or not ANALYTICS_ADMIN_PASSWORD:
            return False
        email_ok    = _hmac.compare_digest(email.lower(),    ANALYTICS_ADMIN_EMAIL.lower())
        password_ok = _hmac.compare_digest(password,         ANALYTICS_ADMIN_PASSWORD)
        return email_ok and password_ok

    async def _fetch_analytics_data() -> dict:
        views = [
            "v_kpi_summary", "v_dau", "v_user_type_ratio", "v_rag_usage",
            "v_top_starters", "v_otp_funnel", "v_memory_extractions", "v_session_stats",
        ]
        async with httpx.AsyncClient(timeout=15.0) as client:
            view_responses, audit_response = await _asyncio.gather(
                _asyncio.gather(*[
                    client.get(f"{SUPABASE_URL}/rest/v1/{v}?select=*", headers=SUPA_HEADERS)
                    for v in views
                ], return_exceptions=True),
                client.get(
                    f"{SUPABASE_URL}/rest/v1/analytics_events"
                    "?event_name=eq.message_sent&order=created_at.desc&limit=500",
                    headers=SUPA_HEADERS,
                ),
            )
        data = {}
        for view, resp in zip(views, view_responses):
            if isinstance(resp, Exception):
                data[view] = []
            elif resp.status_code == 200:
                data[view] = resp.json()
            else:
                data[view] = []
        data["message_audit"] = audit_response.json() if audit_response.status_code == 200 else []
        return data

    class _AnalyticsMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if request.url.path != "/auth/analytics":
                return await call_next(request)
            if request.method == "GET":
                html = _ANALYTICS_LOGIN_HTML.replace("{error_html}", "")
                return _HTMLResponse(html)
            if request.method == "POST":
                form = await request.form()
                email    = (form.get("email")    or "").strip()
                password = (form.get("password") or "").strip()
                if not _check_admin_credentials(email, password):
                    html = _ANALYTICS_LOGIN_HTML.replace(
                        "{error_html}",
                        '<p class="error">Invalid email or password.</p>',
                    )
                    return _HTMLResponse(html, status_code=401)
                data = await _fetch_analytics_data()
                return _HTMLResponse(build_dashboard_html(data))
            return await call_next(request)

    _cl_app.add_middleware(_AnalyticsMiddleware)

    print("[Auth] OTP endpoint registered ✓")
    print("[Analytics] Data endpoint registered at POST /auth/analytics-data ✓")
    print("[Analytics] Dashboard middleware registered at GET/POST /auth/analytics ✓")
except Exception as e:
    print(f"[Auth] OTP endpoint not available: {e}")

# ─────────────────────────────────────────────
# 8. AUTH — Chainlit native login with OTP
# ─────────────────────────────────────────────
@cl.password_auth_callback
def auth_callback(username: str, password: str):
    import asyncio as _asyncio
    loop = _asyncio.get_event_loop()
    # Guest skip
    if password == "guest":
        guest_id = username if username.startswith("guest_") else f"guest_{username}"
        loop.create_task(analytics.log_guest_login())
        return cl.User(identifier=guest_id, metadata={"role": "guest"})
    # OTP login: username = email, password = 6-digit code
    email = username.strip().lower()
    if email and "@" in email and "." in email.split("@")[-1]:
        if _verify_otp_sync(email, password.strip()):
            loop.create_task(analytics.log_otp_verified(email))
            return cl.User(identifier=email, metadata={"role": "user"})
        else:
            loop.create_task(analytics.log_otp_failed())
    return None

# ─────────────────────────────────────────────
# 9. STARTER PROMPTS
# ─────────────────────────────────────────────
@cl.set_starters
async def set_starters():
    import random
    return [
        cl.Starter(label=label, message=message)
        for label, message in random.choice(STARTER_SETS)
    ]


# ─────────────────────────────────────────────
# 10. CHAINLIT HANDLERS
# ─────────────────────────────────────────────
@cl.on_chat_start
async def on_start():
    cl.user_session.set("messages", [])
    cl.user_session.set("response_count", 0)

    user = cl.context.session.user
    is_guest = user.metadata.get("role") == "guest"
    email = None if is_guest else user.identifier
    memories = await _get_memories(email) if email else []
    cl.user_session.set("email", email)
    cl.user_session.set("is_guest", is_guest)
    cl.user_session.set("memories", memories)
    cl.user_session.set("session_started_at", datetime.now(timezone.utc))

    await analytics.log_session_start(
        session_id=cl.context.session.id,
        user_email=email,
        user_type="guest" if is_guest else "registered",
        memory_count=len(memories),
    )


@cl.on_message
async def on_message(message: cl.Message):
    user_text = message.content
    messages = cl.user_session.get("messages", [])
    message_index = len([m for m in messages if m["role"] == "user"])  # 0-based before append
    messages.append({"role": "user", "content": user_text})

    msg = cl.Message(content="", author="Dadi 👵🏾")
    await msg.send()
    full_reply = ""
    rag_used, rag_doc_count = False, 0

    try:
        history_msgs = [
            HumanMessage(content=m["content"]) if m["role"] == "user" else AIMessage(content=m["content"])
            for m in messages[:-1]
        ]

        memories = cl.user_session.get("memories", [])
        memory_section = (
            "\n\n---\nWhat Dadi remembers about this person "
            "(weave naturally into conversation, don't recite all at once):\n"
            + "\n".join(f"- {m}" for m in memories)
        ) if memories else ""

        rag_context = ""
        search_context = ""
        cricket_context = ""
        try:
            is_cricket = _is_cricket_query(user_text)
            tasks = [_retrieve(user_text), _web_search(user_text)]
            if is_cricket:
                tasks.append(_get_cricket_context())
            results = await asyncio.gather(*tasks)
            docs, search_results = results[0], results[1]
            cricket_data = results[2] if is_cricket else ""

            if docs:
                rag_used, rag_doc_count = True, len(docs)
                rag_context = "\n\n---\nDadi's ancient knowledge (use only if relevant):\n" + "\n\n".join(d.page_content for d in docs)
            if search_results:
                search_context = (
                    "\n\n---\nWeb search results (use ONLY if Dadi is genuinely unsure — "
                    "present naturally, not as a list of links):\n" +
                    "\n\n".join(f"{r['title']}: {r['body']}" for r in search_results)
                )
            if cricket_data:
                cricket_context = f"\n\n---\nLive cricket data from CricAPI:\n{cricket_data}"
        except Exception as e:
            print(f"[RAG] Retrieval error: {e}")

        llm_msgs = [SystemMessage(content=DADI_SYSTEM_PROMPT + memory_section + rag_context + search_context + cricket_context)] + history_msgs + [HumanMessage(content=user_text)]
        async for chunk in LLM.astream(llm_msgs):
            full_reply += chunk.content
            await msg.stream_token(chunk.content)

    except Exception as e:
        full_reply = f"*Arre!* Something went wrong beta. (Error: {e})"
        await msg.stream_token(full_reply)

    await msg.update()
    messages.append({"role": "assistant", "content": full_reply})
    cl.user_session.set("messages", messages)

    email = cl.user_session.get("email")
    is_guest = cl.user_session.get("is_guest", True)
    user_type = "guest" if is_guest else "registered"
    response_count = cl.user_session.get("response_count", 0) + 1
    cl.user_session.set("response_count", response_count)

    await analytics.log_message(
        session_id=cl.context.session.id,
        user_email=email,
        user_type=user_type,
        message_index=message_index,
        user_text=user_text,
        rag_used=rag_used,
        rag_doc_count=rag_doc_count,
    )

    if response_count % 6 == 0:
        facts_saved = await _extract_and_save_memories(email, messages)
        cl.user_session.set("memories", await _get_memories(email))
        await analytics.log_memory_extracted(
            session_id=cl.context.session.id,
            user_email=email,
            user_type=user_type,
            facts_count=facts_saved,
            trigger="periodic",
        )


@cl.on_chat_end
async def on_end():
    email = cl.user_session.get("email")
    is_guest = cl.user_session.get("is_guest", True)
    user_type = "guest" if is_guest else "registered"
    messages = cl.user_session.get("messages", [])
    started_at = cl.user_session.get("session_started_at")
    session_id = cl.context.session.id
    user_message_count = len([m for m in messages if m["role"] == "user"])

    if email:
        print(f"[Memory] Session ended — extracting for {email}")
        facts_saved = await _extract_and_save_memories(email, messages)
        await analytics.log_memory_extracted(
            session_id=session_id,
            user_email=email,
            user_type=user_type,
            facts_count=facts_saved,
            trigger="session_end",
        )

    await analytics.log_session_end(
        session_id=session_id,
        user_email=email,
        user_type=user_type,
        message_count=user_message_count,
        started_at=started_at,
    )
