import chainlit as cl
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
import os
import json
import random
import string
import io
import re
import time
import asyncio
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
from prompt import DADI_SYSTEM_PROMPT, STORY_CHAPTER_ADDON, ONBOARDING_ADDON
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from starters import STARTER_SETS
from calendar_context import get_calendar_context
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
LLM_PROVIDER          = os.environ.get("LLM_PROVIDER", "groq").lower()  # "groq", "deepseek", or "novita"
NOVITA_API_KEY        = os.environ.get("NOVITA_API_KEY", "")

analytics.init(SUPABASE_URL, SUPABASE_KEY)

_scheduler = AsyncIOScheduler(timezone="UTC")

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

if LLM_PROVIDER == "novita":
    from langchain_openai import ChatOpenAI
    LLM = ChatOpenAI(
        model="deepseek/deepseek-v3-0324",
        api_key=NOVITA_API_KEY,
        base_url="https://api.novita.ai/v3/openai",
        temperature=0.8,
        streaming=True,
    )
    print("[LLM] Using DeepSeek-V3 via Novita directly")
elif LLM_PROVIDER == "deepseek":
    from langchain_openai import ChatOpenAI
    LLM = ChatOpenAI(
        model="deepseek-ai/DeepSeek-V3:novita",
        api_key=os.environ.get("HUGGINGFACEHUB_API_TOKEN"),
        base_url="https://router.huggingface.co/v1",
        temperature=0.8,
        streaming=True,
    )
    print("[LLM] Using DeepSeek-V3 via HuggingFace router (novita)")
elif LLM_PROVIDER == "gemma":
    from langchain_openai import ChatOpenAI
    LLM = ChatOpenAI(
        model="google/gemma-4-31B-it:novita",
        api_key=os.environ.get("HUGGINGFACEHUB_API_TOKEN"),
        base_url="https://router.huggingface.co/v1",
        temperature=0.8,
        streaming=True,
    )
    print("[LLM] Using Gemma-4-31B-it via HuggingFace router (novita)")
else:
    LLM = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=GROQ_API_KEY,
        temperature=0.8,
        streaming=True,
    )
    print("[LLM] Using Groq (llama-3.3-70b-versatile)")

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
_IPL_DATA_CACHE: dict        = {"data": None, "ts": 0.0}
_IPL_COMMENTARY_CACHE: dict  = {"commentary": [], "overs_snapshot": "", "ts": 0.0}
_CRICKET_KEYWORDS = {
    "cricket", "ipl", "match", "score", "wicket", "batting", "bowling",
    "runs", "t20", "test", "odi", "innings", "over", "boundary", "six",
    "rcb", "csk", "mi", "kkr", "srh", "dc", "pbks", "rr", "gt", "lsg",
    "virat", "rohit", "dhoni", "bumrah", "player of the match",
    "india won", "india lost", "team india", "points table", "standings", "latest scores"
}

def _is_cricket_query(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in _CRICKET_KEYWORDS)

_STORY_KEYWORDS = [
    "kahani", "kahaani", "story", "sunao", "suna do", "kissa",
    "ramayana", "mahabharata", "panchatantra", "lok katha", "folk tale",
    "baat batao", "koi baat", "apne zamane", "purani baat",
]

def _is_story_request(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in _STORY_KEYWORDS)

async def _get_cricket_context() -> str:
    """Fetch live matches + IPL points table from CricAPI. Cached for 120s."""
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


_IPL_DADI_PROMPT = (
    "You are Pushpa Devi Sharma, 68-year-old grandmother from Jaipur, watching IPL on TV. "
    "Give DEADPAN, SAVAGE reactions in 1-2 sentences MAX. "
    "Speak Hinglish (Hindi + English mix). No emojis. No hashtags. "
    "STRICT RULES: "
    "1. React ONLY to facts explicitly in the match data (score, overs, status, team names). "
    "2. Do NOT mention specific player names, wickets, boundaries, or sixes unless stated in the data. "
    "3. Do NOT invent match events, scores, or outcomes not listed. "
    "4. Base reactions on the match situation — high/low score, winning team, match ended, etc. "
    "Reference specific player names and stats from the match data. "
    "Return ONLY a valid JSON array of exactly 6 objects — no markdown, no backticks:\n"
    '[{"reaction": "...", "context": "..."}]'
)

_IPL_PRESET_REACTIONS = [
    {"reaction": "Koi baat nahi beta, haar ke bhi sikhte hain. Mera beta bhi class mein last aata tha, ab bank mein kaam karta hai.", "context": "Match update"},
    {"reaction": "Itne paison mein toh main poora mohalla khila deti. Aur yeh log bat se ball bhi nahi maar pa rahe.", "context": "IPL auction money"},
    {"reaction": "Stadium mein itni roshni hai. Hamare zamane mein load-shedding mein cricket khelte the, phir bhi zyada maza tha.", "context": "Night match"},
]

async def _get_ipl_match_data() -> dict | None:
    """Fetch structured IPL match data. Cached for 120s."""
    cricapi_key = os.environ.get("CRICAPI_KEY", "")
    if not cricapi_key:
        return None
    now = time.time()
    if _IPL_DATA_CACHE["data"] and now - _IPL_DATA_CACHE["ts"] < _CRICKET_TTL:
        return _IPL_DATA_CACHE["data"]
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            matches_resp, series_resp = await asyncio.gather(
                client.get("https://api.cricapi.com/v1/currentMatches",
                           params={"apikey": cricapi_key, "offset": 0}),
                client.get("https://api.cricapi.com/v1/series",
                           params={"apikey": cricapi_key, "offset": 0, "search": "IPL"}),
                return_exceptions=True,
            )

        result: dict = {"matches": [], "points_table": []}

        if not isinstance(matches_resp, Exception) and matches_resp.status_code == 200:
            mdata = matches_resp.json()
            if mdata.get("status") == "success":
                all_matches = mdata.get("data", [])
                _ipl_kw = ("ipl", "indian premier league", "tata ipl")
                ipl_matches = [
                    m for m in all_matches
                    if any(kw in m.get("name", "").lower() for kw in _ipl_kw)
                    or any(kw in (m.get("series", "") or "").lower() for kw in _ipl_kw)
                ]
                # Fallback: if nothing matched by name, log all match names for debugging
                if not ipl_matches:
                    print("[IPL] No IPL match found. Available matches:", [m.get("name") for m in all_matches])
                display = ipl_matches if ipl_matches else []
                for m in display:
                    result["matches"].append({
                        "name":   m.get("name", ""),
                        "status": m.get("status", ""),
                        "venue":  m.get("venue", ""),
                        "date":   m.get("date", ""),
                        "score":  m.get("score", []),
                        "teams":  m.get("teams", []),
                        "tossChoice": m.get("tossChoice", ""),
                        "matchStarted": m.get("matchStarted", False),
                        "matchEnded":   m.get("matchEnded", False),
                    })

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
                    for row in pdata.get("data", []):
                        result["points_table"].append({
                            "team": row.get("teamName") or row.get("team", ""),
                            "p":    row.get("p") or row.get("matchesPlayed", 0),
                            "w":    row.get("w") or row.get("win", 0),
                            "l":    row.get("l") or row.get("loss", 0),
                            "pts":  row.get("pts") or row.get("points", 0),
                        })

        result["fetched_at"] = int(now)

        if result["matches"]:
            # Match found — cache it. If ended, keep it for 2 hours so
            # post-match commentary stays visible after it leaves currentMatches.
            match_ended = any(m.get("matchEnded") for m in result["matches"])
            _IPL_DATA_CACHE["data"] = result
            _IPL_DATA_CACHE["ts"]   = now if not match_ended else now - _CRICKET_TTL + 7200
        elif _IPL_DATA_CACHE["data"]:
            # No IPL match in API response — keep serving last known data
            # for up to 2 hours so the page doesn't go blank right after a match ends.
            last_ts = _IPL_DATA_CACHE["ts"]
            if now - last_ts < 7200:
                print("[IPL] No live match found, serving cached data from last match")
                return _IPL_DATA_CACHE["data"]
            # Cache expired — clear it
            _IPL_DATA_CACHE["data"] = None

        return result
    except Exception as e:
        print(f"[IPL] Data fetch failed: {e}")
        # On error, return stale cache if available rather than None
        if _IPL_DATA_CACHE["data"]:
            print("[IPL] Returning stale cache after fetch error")
            return _IPL_DATA_CACHE["data"]
        return None


async def _get_ipl_commentary(match_data: dict) -> list[dict]:
    """Generate Dadi's IPL commentary via LLM. Cached until overs change."""
    if not match_data or not match_data.get("matches"):
        return _IPL_PRESET_REACTIONS

    # Build overs snapshot to detect score changes
    snap_parts = []
    for m in match_data["matches"]:
        for s in m.get("score", []):
            snap_parts.append(f"{s.get('inning','')[:10]}:{s.get('o','')}")
    overs_snapshot = "|".join(snap_parts)

    now = time.time()
    match_ended = any(m.get("matchEnded") for m in match_data.get("matches", []))
    # After match ends, keep commentary for 2 hours (no point regenerating)
    commentary_ttl = 7200 if match_ended else 600
    if (
        _IPL_COMMENTARY_CACHE["commentary"]
        and _IPL_COMMENTARY_CACHE["overs_snapshot"] == overs_snapshot
        and now - _IPL_COMMENTARY_CACHE["ts"] < commentary_ttl
    ):
        return _IPL_COMMENTARY_CACHE["commentary"]

    # Build match summary for the prompt
    summary_lines = []
    for m in match_data["matches"][:2]:
        summary_lines.append(f"Match: {m['name']} — {m['status']}")
        if m.get("venue"):
            summary_lines.append(f"Venue: {m['venue']}")
        for s in m.get("score", []):
            summary_lines.append(
                f"  {s.get('inning','')}: {s.get('r','')}/{s.get('w','')} ({s.get('o','')} ov)"
            )
    if match_data.get("points_table"):
        summary_lines.append("IPL Points Table (top 5):")
        for row in match_data["points_table"][:5]:
            summary_lines.append(f"  {row['team']}: P{row['p']} W{row['w']} L{row['l']} Pts{row['pts']}")

    match_summary = "\n".join(summary_lines)

    try:
        llm_msgs = [
            SystemMessage(content=_IPL_DADI_PROMPT),
            HumanMessage(content=f"Live match data:\n{match_summary}\n\nGenerate 6 reactions based ONLY on this data. Do not add player names or events not listed above. Return ONLY a JSON array: [{{\"reaction\": \"...\", \"context\": \"...\"}}]"),
        ]
        result = await asyncio.wait_for(LLM.ainvoke(llm_msgs), timeout=30.0)
        text = result.content.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        parsed = json.loads(text.strip())
        if isinstance(parsed, list) and parsed:
            _IPL_COMMENTARY_CACHE["commentary"]      = parsed
            _IPL_COMMENTARY_CACHE["overs_snapshot"]  = overs_snapshot
            _IPL_COMMENTARY_CACHE["ts"]              = now
            return parsed
    except Exception as e:
        print(f"[IPL] Commentary LLM failed: {e}")

    return _IPL_COMMENTARY_CACHE["commentary"] or _IPL_PRESET_REACTIONS


async def _web_search(query: str, max_results: int = 3) -> list[dict]:
    """DuckDuckGo search, returns list of {title, body, href}. Never raises."""
    try:
        from ddgs import DDGS
        loop = asyncio.get_event_loop()
        results = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: list(DDGS().text(query, max_results=max_results))),
            timeout=6.0,
        )
        return results
    except asyncio.TimeoutError:
        print("[Search] DuckDuckGo timed out")
        return []
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
# 5b. USER PREFERENCES (daily email opt-in)
# ─────────────────────────────────────────────
async def _get_daily_optin(email: str) -> bool:
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{SUPABASE_URL}/rest/v1/user_preferences?user_email=eq.{email}&select=daily_optin",
                headers=SUPA_HEADERS, timeout=10,
            )
        rows = r.json()
        return bool(rows[0]["daily_optin"]) if rows else False
    except Exception:
        return False

async def _set_daily_optin(email: str, value: bool):
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{SUPABASE_URL}/rest/v1/user_preferences",
                headers={**SUPA_HEADERS, "Prefer": "resolution=merge-duplicates"},
                json={
                    "user_email": email,
                    "daily_optin": value,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                timeout=10,
            )
    except Exception as e:
        print(f"[Prefs] Save error: {e}")

async def _get_all_daily_optin_emails() -> list:
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{SUPABASE_URL}/rest/v1/user_preferences?daily_optin=eq.true&select=user_email",
                headers=SUPA_HEADERS, timeout=15,
            )
        return [row["user_email"] for row in r.json()]
    except Exception as e:
        print(f"[Daily] Failed to fetch opted-in users: {e}")
        return []

async def _send_daily_dadi_email(email: str, content: str):
    if not RESEND_API_KEY:
        return
    async with httpx.AsyncClient() as client:
        await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
            json={
                "from": EMAIL_FROM,
                "to": [email],
                "subject": "☀️ Dadi ka subah ka sandesh",
                "html": (
                    '<div style="font-family:Georgia,serif;max-width:480px;margin:0 auto;'
                    'padding:24px;background:#FDF6F0;border-radius:12px;">'
                    '<p style="font-size:0.8rem;color:#9e7a5a;letter-spacing:0.1em;'
                    'text-transform:uppercase;margin-bottom:16px;">Dadi AI — Subah ka Sandesh</p>'
                    f'<p style="font-size:1.1rem;color:#2d1a10;line-height:1.7;">{content}</p>'
                    '<hr style="border:none;border-top:1px solid #f0d9c8;margin:24px 0;">'
                    '<p style="font-size:0.78rem;color:#9e7a5a;">'
                    'Aana kabhi — <a href="https://www.mydadi.in" style="color:#8B1A1A;">mydadi.in</a> pe intezaar hai.<br>'
                    '<a href="https://www.mydadi.in/profile" style="color:#9e7a5a;font-size:0.72rem;">'
                    'Emails band karne ke liye profile visit karo</a></p></div>'
                ),
            },
            timeout=15,
        )

async def _run_daily_dadi_emails():
    print("[Daily] Generating daily message...")
    cal = get_calendar_context()
    prompt = (
        "Write one short morning message (3-4 sentences) as Dadi — Pushpa Devi Sharma, 68, Jaipur. "
        "Hinglish voice. Could be a seasonal blessing, a proverb with a warm twist, or a gentle observation. "
        "Today's context:\n" + cal + "\nNo greeting opener like 'Good morning'. Just the message itself."
    )
    try:
        response = await LLM.ainvoke([HumanMessage(content=prompt)])
        content = response.content.strip()
    except Exception as e:
        print(f"[Daily] LLM error: {e}")
        return
    emails = await _get_all_daily_optin_emails()
    print(f"[Daily] Sending to {len(emails)} users")
    for email in emails:
        try:
            await _send_daily_dadi_email(email, content)
        except Exception as e:
            print(f"[Daily] Failed for {email}: {e}")

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
        asyncio.create_task(analytics.log_otp_requested(email))
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
        return JSONResponse(await _fetch_analytics_data())

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
            view_responses, audit_response = await asyncio.gather(
                asyncio.gather(*[
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

    _MANIFEST_JSON = json.dumps({
        "name": "Dadi AI",
        "short_name": "Dadi AI",
        "description": "Your wise AI Indian grandmother — advice, recipes, stories, and desi wisdom.",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#FDF6F0",
        "theme_color": "#8B1A1A",
        "orientation": "portrait-primary",
        "lang": "en-IN",
        "icons": [
            {"src": "/public/favicon.png",     "sizes": "64x64", "type": "image/png"},
            {"src": "/public/logo_dark.png",   "sizes": "any",   "type": "image/png", "purpose": "any"},
            {"src": "/public/images/dadi.png", "sizes": "any",   "type": "image/png", "purpose": "any maskable"},
        ],
        "categories": ["lifestyle", "social"],
        "shortcuts": [{"name": "Chat with Dadi", "url": "/", "description": "Start a new conversation"}],
    })

    _SW_JS = r"""
const CACHE = 'dadi-v1';
const PRECACHE = [
  '/public/favicon.png',
  '/public/logo_dark.png',
  '/public/logo_light.png',
  '/public/custom.css',
  '/public/images/dadi.png',
  '/public/images/dadi_dancing.png',
  '/public/images/dadi_karate.png',
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE)
      .then(c => c.addAll(PRECACHE.map(u => new Request(u, {cache: 'reload'}))))
      .then(() => self.skipWaiting())
      .catch(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  const url = new URL(e.request.url);
  if (url.pathname.startsWith('/auth') ||
      url.pathname.startsWith('/ws') ||
      url.pathname.startsWith('/login') ||
      url.pathname.startsWith('/api') ||
      url.pathname.includes('socket')) return;

  if (url.pathname.startsWith('/public/')) {
    e.respondWith(
      caches.match(e.request).then(cached => {
        if (cached) return cached;
        return fetch(e.request).then(res => {
          if (res.ok) { const clone = res.clone(); caches.open(CACHE).then(c => c.put(e.request, clone)); }
          return res;
        });
      })
    );
    return;
  }

  e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
});
"""

    _SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:xhtml="http://www.w3.org/1999/xhtml">
  <url>
    <loc>https://www.mydadi.in/</loc>
    <lastmod>2026-04-01</lastmod>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
    <xhtml:link rel="alternate" hreflang="en" href="https://www.mydadi.in/"/>
    <xhtml:link rel="alternate" hreflang="hi" href="https://www.mydadi.in/"/>
  </url>
  <url>
    <loc>https://www.mydadi.in/ipl</loc>
    <lastmod>2026-04-08</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.8</priority>
  </url>
</urlset>"""

    _IPL_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dadi ka IPL — mydadi.in</title>
<meta name="description" content="Live IPL scores with Dadi's deadpan Hinglish commentary. She will roast your favourite team.">
<meta property="og:title" content="Dadi ka IPL">
<meta property="og:description" content="Live IPL commentary your grandmother never asked for.">
<meta property="og:url" content="https://www.mydadi.in/ipl">
<meta property="og:type" content="website">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Tiro+Devanagari+Hindi:ital@0;1&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0A0A0A;font-family:'DM Sans',sans-serif;color:#fff;min-height:100vh}
.hero{background:linear-gradient(180deg,#7F1D1D 0%,#450a0a 60%,#0A0A0A 100%);padding:40px 20px 60px;text-align:center;position:relative;overflow:hidden}
.live-badge{display:inline-flex;align-items:center;gap:8px;background:rgba(251,191,36,0.15);border:1px solid rgba(251,191,36,0.3);border-radius:100px;padding:6px 16px;margin-bottom:16px}
.live-dot{width:8px;height:8px;border-radius:50%;background:#EF4444;animation:pulse 1.5s infinite}
.live-text{font-size:12px;color:#FBBF24;font-weight:600;letter-spacing:1px}
h1{font-family:'Tiro Devanagari Hindi',serif;font-size:36px;color:#fff;margin:0 0 4px;line-height:1.2}
.subtitle{font-size:14px;color:rgba(255,255,255,0.5);margin:0 0 24px}
.scoreboard{background:rgba(255,255,255,0.06);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.1);border-radius:16px;padding:20px 24px;max-width:420px;margin:0 auto}
.scores{display:flex;justify-content:space-between;align-items:center}
.team-name{font-size:28px;font-weight:800}
.team-score{font-size:22px;font-weight:700;margin-top:2px}
.team-overs{font-size:11px;color:rgba(255,255,255,0.4);margin-top:2px}
.vs{font-size:13px;font-weight:700;color:rgba(255,255,255,0.3);padding:4px 12px;border:1px solid rgba(255,255,255,0.1);border-radius:8px}
.match-status{margin-top:12px;padding-top:12px;border-top:1px solid rgba(255,255,255,0.08);font-size:12px;color:#EF4444;font-weight:600}
.match-venue{font-size:11px;color:rgba(255,255,255,0.3);margin-top:4px}
.match-name-display{font-size:13px;color:rgba(255,255,255,0.6);margin-top:4px;font-weight:500}
.content{padding:0 16px 40px;max-width:500px;margin:0 auto}
.section-header{display:flex;justify-content:space-between;align-items:center;margin:-30px 0 20px}
.section-title{font-family:'Tiro Devanagari Hindi',serif;font-size:22px;color:#fff}
.refresh-btn{padding:8px 16px;border-radius:10px;border:none;background:#FBBF24;color:#1a1a1a;font-size:12px;font-weight:700;cursor:pointer;font-family:'DM Sans',sans-serif;transition:all 0.2s}
.refresh-btn:disabled{background:rgba(251,191,36,0.2);color:#FBBF24;cursor:default}
.reactions{display:flex;flex-direction:column;gap:12px}
.reaction-card{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:14px;padding:18px 20px;cursor:pointer;transition:all 0.2s}
.reaction-card:hover{background:rgba(255,255,255,0.08);border-color:rgba(251,191,36,0.3)}
.reaction-context{font-size:10px;font-weight:700;color:#FBBF24;letter-spacing:0.5px;margin-bottom:8px;text-transform:uppercase}
.reaction-text{font-family:'Tiro Devanagari Hindi',serif;font-size:16px;line-height:1.7;color:rgba(255,255,255,0.9)}
.copy-hint{font-size:10px;color:rgba(255,255,255,0.25);margin-top:10px;display:flex;align-items:center;gap:4px}
.highlights{margin-top:32px}
.highlights h3{font-family:'Tiro Devanagari Hindi',serif;font-size:18px;color:#fff;margin:0 0 14px}
.highlights-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.highlight-card{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:14px 16px}
.hl-label{font-size:12px;color:rgba(255,255,255,0.4);margin-bottom:4px}
.hl-value{font-size:22px;font-weight:800}
.hl-sub{font-size:11px;color:rgba(255,255,255,0.3);margin-top:2px}
.points-table{margin-top:24px}
.points-table h3{font-family:'Tiro Devanagari Hindi',serif;font-size:18px;color:#fff;margin:0 0 14px}
.pt-row{display:flex;justify-content:space-between;align-items:center;padding:10px 14px;background:rgba(255,255,255,0.03);border-radius:8px;margin-bottom:6px;font-size:13px}
.pt-team{font-weight:600;color:rgba(255,255,255,0.9)}
.pt-stats{color:rgba(255,255,255,0.4);font-size:12px}
.pt-pts{font-weight:700;color:#FBBF24;min-width:30px;text-align:right}
.cta-box{margin-top:32px;background:linear-gradient(135deg,rgba(251,191,36,0.1),rgba(251,191,36,0.05));border:1px solid rgba(251,191,36,0.2);border-radius:16px;padding:24px 20px;text-align:center}
.cta-box h3{font-family:'Tiro Devanagari Hindi',serif;font-size:18px;color:#fff;margin:12px 0 6px}
.cta-box p{font-size:13px;color:rgba(255,255,255,0.5);margin-bottom:16px;line-height:1.5}
.cta-link{display:inline-block;padding:12px 28px;border-radius:10px;background:#FBBF24;color:#1a1a1a;text-decoration:none;font-weight:700;font-size:14px}
.footer{text-align:center;margin-top:32px;padding-top:20px;border-top:1px solid rgba(255,255,255,0.06);font-size:11px;color:rgba(255,255,255,0.2)}
.error-box{padding:20px;text-align:center;color:rgba(255,255,255,0.4);font-size:14px;margin:20px 0}
.loading-box{padding:20px;text-align:center;color:#FBBF24;font-size:14px}
.no-match-box{padding:40px 20px;text-align:center}
.no-match-box p{font-family:'Tiro Devanagari Hindi',serif;font-size:18px;color:rgba(255,255,255,0.7);line-height:1.6}
.toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#16A34A;color:#fff;padding:10px 20px;border-radius:8px;font-size:13px;font-weight:600;opacity:0;transition:opacity 0.3s;pointer-events:none;z-index:999}
.toast.show{opacity:1}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:0.5;transform:scale(0.8)}}
</style>
</head>
<body>
<div class="hero">
  <div class="live-badge">
    <div class="live-dot" id="live-dot"></div>
    <span class="live-text" id="live-text">IPL 2026</span>
  </div>
  <h1>Dadi ka IPL</h1>
  <p class="subtitle">Cricket commentary your grandmother never asked for</p>
  <div class="scoreboard" id="scoreboard">
    <div class="loading-box">Dadi TV on kar rahi hai...</div>
  </div>
</div>

<div class="content">
  <div class="section-header">
    <h2 class="section-title">&#x1F475;&#x1F3FE; Dadi bol rahi hai...</h2>
    <button class="refresh-btn" id="refresh-btn" onclick="refreshData()">Aur sunao</button>
  </div>
  <div class="reactions" id="reactions">
    <div class="loading-box">Dadi soch rahi hai...</div>
  </div>
  <div id="highlights-section"></div>
  <div id="points-section"></div>
  <div class="cta-box">
    <div style="font-size:28px">&#x1F475;&#x1F3FE;</div>
    <h3>Dadi se baat karo</h3>
    <p>IPL hi nahi, life ke baare mein bhi Dadi ke paas opinion hai</p>
    <a href="/" class="cta-link">Chat with Dadi &rarr;</a>
  </div>
  <div class="footer">mydadi.in &bull; Dadi AI &bull; Made with pyaar &amp; thoda masala</div>
</div>

<div class="toast" id="toast">Copied!</div>

<script>
let lastOversSnapshot = '';
let isRefreshing = false;

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2000);
}

function copyReaction(text, context) {
  const full = '"' + text + '" — Dadi on ' + context + '\\n\\nmydadi.in/ipl';
  navigator.clipboard.writeText(full).then(() => showToast('WhatsApp ke liye copy ho gaya!')).catch(() => showToast('Copy failed'));
}

function renderScoreboard(data) {
  const sb = document.getElementById('scoreboard');
  const liveDot = document.getElementById('live-dot');
  const liveText = document.getElementById('live-text');

  if (!data.matches || !data.matches.length) {
    sb.innerHTML = '<div class="no-match-box"><p>Abhi koi IPL match nahi chal raha.<br>Dadi chai pi rahi hain.</p></div>';
    liveDot.style.background = '#6B7280';
    liveText.textContent = 'IPL 2026';
    return;
  }

  const m = data.matches[0];
  const teams = m.teams || [];
  const scores = m.score || [];
  const isLive = m.matchStarted && !m.matchEnded;

  liveDot.style.background = isLive ? '#EF4444' : '#6B7280';
  liveText.textContent = isLive ? 'LIVE \u2022 IPL 2026' : 'IPL 2026';

  // Map score by innings
  const scoreMap = {};
  scores.forEach(s => {
    const inning = s.inning || '';
    const teamCode = inning.split(' ')[0];
    scoreMap[teamCode] = s;
  });

  const t1 = teams[0] || 'Team 1';
  const t2 = teams[1] || 'Team 2';
  const s1 = scoreMap[t1] || scoreMap[Object.keys(scoreMap)[0]] || {};
  const s2 = scoreMap[t2] || scoreMap[Object.keys(scoreMap)[1]] || {};

  const fmt = (s) => s.r !== undefined ? s.r + '/' + s.w : '--';
  const overs = (s) => s.o !== undefined ? '(' + s.o + ' ov)' : '';
  const col1 = scores.length > 0 ? '#FBBF24' : 'rgba(255,255,255,0.6)';
  const col2 = scores.length > 1 ? '#EF4444' : 'rgba(255,255,255,0.6)';

  sb.innerHTML = `
    <div class="scores">
      <div style="text-align:left">
        <div class="team-name">${t1}</div>
        <div class="team-score" style="color:${col1}">${fmt(s1)}</div>
        <div class="team-overs">${overs(s1)}</div>
      </div>
      <div class="vs">vs</div>
      <div style="text-align:right">
        <div class="team-name">${t2}</div>
        <div class="team-score" style="color:${col2}">${fmt(s2)}</div>
        <div class="team-overs">${overs(s2)}</div>
      </div>
    </div>
    <div class="match-name-display">${m.name || ''}</div>
    <div class="match-status">${m.status || ''}</div>
    <div class="match-venue">${m.venue || ''}</div>
  `;
}

function renderReactions(commentary) {
  const el = document.getElementById('reactions');
  if (!commentary || !commentary.length) {
    el.innerHTML = '<div class="error-box">Dadi abhi kuch nahi bol rahi. Thodi der mein aao.</div>';
    return;
  }
  el.innerHTML = commentary.map(r => `
    <div class="reaction-card" onclick="copyReaction(${JSON.stringify(r.reaction)}, ${JSON.stringify(r.context)})">
      <div class="reaction-context">${r.context || ''}</div>
      <div class="reaction-text">"${r.reaction || ''}"</div>
      <div class="copy-hint"><span>Tap to copy for WhatsApp</span><span style="font-size:12px">\u2192</span></div>
    </div>
  `).join('');
}

function renderPointsTable(table) {
  const el = document.getElementById('points-section');
  if (!table || !table.length) { el.innerHTML = ''; return; }
  el.innerHTML = `
    <div class="points-table">
      <h3>IPL Points Table</h3>
      ${table.slice(0, 10).map(r => `
        <div class="pt-row">
          <span class="pt-team">${r.team}</span>
          <span class="pt-stats">P${r.p} W${r.w} L${r.l}</span>
          <span class="pt-pts">${r.pts} pts</span>
        </div>
      `).join('')}
    </div>
  `;
}

async function fetchData(force) {
  const btn = document.getElementById('refresh-btn');
  btn.disabled = true;
  btn.textContent = 'Soch rahi hai...';
  isRefreshing = true;

  try {
    // Step 1: fetch live score immediately — no LLM wait
    const scoreRes = await fetch('/ipl/score');
    if (scoreRes.ok) {
      const scoreData = await scoreRes.json();
      renderScoreboard(scoreData);
      renderPointsTable(scoreData.points_table);
      lastOversSnapshot = scoreData.overs_snapshot || '';
    }

    // Step 2: fetch Dadi's commentary (LLM call, may take a moment)
    document.getElementById('reactions').innerHTML = '<div class="loading-box">Dadi soch rahi hai...</div>';
    const url = '/ipl/data' + (force ? '?force=1' : '');
    const res = await fetch(url);
    if (!res.ok) throw new Error('fetch failed');
    const data = await res.json();

    renderScoreboard(data);
    renderReactions(data.commentary);
    renderPointsTable(data.points_table);
    lastOversSnapshot = data.overs_snapshot || '';
  } catch(e) {
    console.error('[IPL]', e);
    document.getElementById('reactions').innerHTML = '<div class="error-box">Network error. Dadi ka signal thoda weak hai.</div>';
  }

  btn.disabled = false;
  btn.textContent = 'Aur sunao';
  isRefreshing = false;
}

function refreshData() { fetchData(true); }

// Initial load
fetchData(false);

// Auto-refresh every 2 minutes; only re-render if overs changed
setInterval(async () => {
  if (isRefreshing) return;
  try {
    const res = await fetch('/ipl/data');
    if (!res.ok) return;
    const data = await res.json();
    if (data.overs_snapshot !== lastOversSnapshot) {
      renderScoreboard(data);
      renderReactions(data.commentary);
      renderPointsTable(data.points_table);
      lastOversSnapshot = data.overs_snapshot || '';
    } else {
      // Still update scoreboard status (might have changed without overs changing)
      renderScoreboard(data);
    }
  } catch(e) {}
}, 120000);
</script>
</body>
</html>"""

    from starlette.responses import Response as _XMLResponse

    class _AnalyticsMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if request.url.path == "/manifest.json":
                return JSONResponse(content=json.loads(_MANIFEST_JSON), media_type="application/manifest+json")
            if request.url.path == "/sw.js":
                return _XMLResponse(content=_SW_JS, media_type="application/javascript")
            if request.url.path == "/sitemap.xml":
                return _XMLResponse(content=_SITEMAP_XML, media_type="application/xml")

            # IPL page — must be before Chainlit SPA catch-all
            if request.url.path == "/ipl":
                return _HTMLResponse(_IPL_PAGE_HTML)
            if request.url.path == "/ipl/score":
                # Live score only — no LLM, fast response
                match_data = await _get_ipl_match_data()
                snap_parts = []
                if match_data:
                    for m in match_data.get("matches", []):
                        for s in m.get("score", []):
                            snap_parts.append(f"{s.get('inning','')[:10]}:{s.get('o','')}")
                return JSONResponse({
                    "matches":        (match_data or {}).get("matches", []),
                    "points_table":   (match_data or {}).get("points_table", []),
                    "overs_snapshot": "|".join(snap_parts),
                    "fetched_at":     int(time.time()),
                })
            if request.url.path == "/ipl/data":
                match_data = await _get_ipl_match_data()
                commentary = await _get_ipl_commentary(match_data or {})
                snap_parts = []
                if match_data:
                    for m in match_data.get("matches", []):
                        for s in m.get("score", []):
                            snap_parts.append(f"{s.get('inning','')[:10]}:{s.get('o','')}")
                payload = {
                    "matches":        (match_data or {}).get("matches", []),
                    "points_table":   (match_data or {}).get("points_table", []),
                    "commentary":     commentary,
                    "overs_snapshot": "|".join(snap_parts),
                    "fetched_at":     int(time.time()),
                }
                return JSONResponse(payload)
            if request.url.path == "/ipl/debug":
                # Raw CricAPI response for debugging
                cricapi_key = os.environ.get("CRICAPI_KEY", "")
                if not cricapi_key:
                    return JSONResponse({"error": "CRICAPI_KEY not set"})
                async with httpx.AsyncClient(timeout=10.0) as client:
                    r = await client.get("https://api.cricapi.com/v1/currentMatches",
                                         params={"apikey": cricapi_key, "offset": 0})
                return JSONResponse(r.json())

            # Share card routes — must be handled here (before Chainlit SPA catch-all)
            if request.url.path.startswith("/card/"):
                cid = request.url.path[len("/card/"):]
                png = await _load_card(cid)
                if not png:
                    return JSONResponse({"error": "Card not found"}, status_code=404)
                return _XMLResponse(content=png, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})
            if request.url.path.startswith("/share/"):
                cid = request.url.path[len("/share/"):]
                png = await _load_card(cid)
                base = str(request.base_url).rstrip("/")
                img_url   = f"{base}/card/{cid}"
                share_url = f"{base}/share/{cid}"
                if not png:
                    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Dadi Ne Bola</title></head>
<body style="font-family:Georgia,serif;text-align:center;padding:40px;background:#FDF6F0;color:#8B1A1A">
<h2>Arre beta, yeh card nahi mila!</h2><p>Shayad link purana ho gaya. <a href="/">Wapas Dadi ke paas aa.</a></p>
</body></html>"""
                    return _HTMLResponse(html, status_code=404)
                html = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dadi Ne Bola — mydadi.in</title>
<meta property="og:title" content="Dadi Ne Bola">
<meta property="og:description" content="Chat with Dadi — she will roast you, love you, and fix you. mydadi.in">
<meta property="og:image" content="{img_url}">
<meta property="og:image:width" content="800"><meta property="og:image:height" content="480">
<meta property="og:url" content="{share_url}"><meta property="og:type" content="website">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="{img_url}">
<style>body{{margin:0;background:#FDF6F0;font-family:Georgia,serif;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;padding:24px}}
img{{max-width:100%;border-radius:12px;box-shadow:0 8px 40px rgba(139,26,26,.15)}}
a.cta{{display:inline-block;margin-top:20px;padding:12px 28px;background:#8B1A1A;color:#fff;border-radius:8px;text-decoration:none;font-size:1rem}}
p{{color:#9e7a5a;font-size:.85rem;margin-top:12px}}</style>
</head><body>
<img src="{img_url}" alt="Dadi Ne Bola">
<a class="cta" href="/">Aaja, Dadi se baat kar →</a>
<p>mydadi.in — She will roast you. She will fix you.</p>
</body></html>"""
                return _HTMLResponse(html)

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

    # ── Profile page ──────────────────────────────────────────────────────────
    _PROFILE_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Meri Profile — Dadi AI</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600&family=Kalam:wght@400;700&family=Inter:wght@400;500&display=swap" rel="stylesheet">
<style>
  *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'Inter',sans-serif;background:#FDF6F0;color:#2d1a10;min-height:100vh;padding:24px 16px}
  .wrap{max-width:520px;margin:0 auto}
  .logo{font-family:'Playfair Display',serif;color:#8B1A1A;font-size:1.4rem;text-align:center;margin-bottom:4px}
  .tagline{text-align:center;font-size:0.75rem;color:#9e7a5a;letter-spacing:.12em;text-transform:uppercase;margin-bottom:28px}
  .card{background:#fff;border:1px solid #f0d9c8;border-radius:16px;padding:24px;margin-bottom:16px;box-shadow:0 4px 20px rgba(139,26,26,.06)}
  .card h2{font-family:'Playfair Display',serif;color:#8B1A1A;font-size:1.1rem;margin-bottom:14px}
  .field{margin-bottom:14px}
  label{display:block;font-size:0.78rem;color:#9e7a5a;text-transform:uppercase;letter-spacing:.05em;margin-bottom:5px}
  input[type=email]{width:100%;padding:0.65rem 0.9rem;border:1px solid #f0d9c8;border-radius:8px;font-size:0.95rem;outline:none;transition:border-color .2s}
  input[type=email]:focus{border-color:#8B1A1A}
  button[type=submit]{width:100%;padding:0.7rem;background:linear-gradient(135deg,#8B1A1A,#c0392b);color:#fff;border:none;border-radius:8px;font-size:0.95rem;font-weight:600;cursor:pointer;margin-top:4px}
  .error{color:#c0392b;font-size:0.82rem;margin-top:10px;text-align:center}
  .memory-list{list-style:none;padding:0}
  .memory-list li{padding:8px 12px;background:#FDF6F0;border-radius:8px;margin-bottom:6px;font-size:0.9rem;color:#2d1a10;border-left:3px solid #8B1A1A}
  .stat-row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #f0d9c8;font-size:0.9rem}
  .stat-row:last-child{border-bottom:none}
  .stat-val{font-weight:600;color:#8B1A1A}
  .toggle-label{display:flex;align-items:center;gap:10px;cursor:pointer;font-size:0.9rem}
  .toggle-label input[type=checkbox]{width:18px;height:18px;accent-color:#8B1A1A;cursor:pointer}
  .back{display:block;text-align:center;margin-top:20px;font-size:0.8rem;color:#9e7a5a;text-decoration:none}
  .back:hover{color:#8B1A1A}
</style>
</head>
<body>
<div class="wrap">
  <div class="logo">Dadi AI</div>
  <div class="tagline">She will roast you. She will fix you.</div>
  <div class="card">
    <h2>Meri Profile</h2>
    <form method="POST" action="/profile">
      <div class="field">
        <label for="email">Apna email daalo</label>
        <input type="email" id="email" name="email" placeholder="beta@example.com" autofocus required>
      </div>
      <button type="submit">Dekho kya yaad hai Dadi ko</button>
      {error_html}
    </form>
  </div>
  {profile_html}
  <a href="/" class="back">← Wapas Dadi ke paas</a>
</div>
</body>
</html>"""

    @_cl_app.get("/profile")
    async def profile_get(request: Request):
        email_param = request.query_params.get("email", "")
        if email_param:
            return await _render_profile(email_param)
        return _HTMLResponse(_PROFILE_PAGE_HTML.replace("{error_html}", "").replace("{profile_html}", ""))

    @_cl_app.post("/profile")
    async def profile_post(request: Request):
        form = await request.form()
        email = (form.get("email") or "").strip().lower()
        if not email or "@" not in email:
            return _HTMLResponse(
                _PROFILE_PAGE_HTML.replace("{error_html}", '<p class="error">Valid email daalo beta.</p>').replace("{profile_html}", "")
            )
        return await _render_profile(email)

    async def _render_profile(email: str):
        memories = await _get_memories(email)
        optin = await _get_daily_optin(email)
        total_sessions = 0
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    f"{SUPABASE_URL}/rest/v1/analytics_events?user_email=eq.{email}&event_name=eq.session_start&select=id",
                    headers=SUPA_HEADERS, timeout=10,
                )
                if r.status_code == 200:
                    total_sessions = len(r.json())
        except Exception:
            pass

        memories_html = (
            "".join(f'<li>{m}</li>' for m in memories)
            if memories else
            "<li style='color:#9e7a5a;border-left-color:#f0d9c8;'>Abhi kuch yaad nahi — aaja baat kar!</li>"
        )
        optin_checked = "checked" if optin else ""
        profile_html = f"""
        <div class="card">
          <h2>Dadi ko yaad hai…</h2>
          <ul class="memory-list">{memories_html}</ul>
        </div>
        <div class="card">
          <h2>Teri stats</h2>
          <div class="stat-row"><span>Total sessions</span><span class="stat-val">{total_sessions}</span></div>
          <div class="stat-row"><span>Memories saved</span><span class="stat-val">{len(memories)}</span></div>
        </div>
        <div class="card">
          <h2>Roz subah ka sandesh ☀️</h2>
          <form method="POST" action="/toggle-daily-email">
            <input type="hidden" name="email" value="{email}">
            <label class="toggle-label">
              <input type="checkbox" name="daily_optin" {optin_checked} onchange="this.form.submit()">
              Dadi ka roz subah email bhejo
            </label>
          </form>
        </div>"""
        return _HTMLResponse(
            _PROFILE_PAGE_HTML.replace("{error_html}", "").replace("{profile_html}", profile_html)
        )

    @_cl_app.post("/toggle-daily-email")
    async def toggle_daily_email(request: Request):
        from starlette.responses import RedirectResponse
        form = await request.form()
        email = (form.get("email") or "").strip().lower()
        value = form.get("daily_optin") == "on"
        if email:
            await _set_daily_optin(email, value)
        return RedirectResponse(url=f"/profile?email={email}", status_code=303)

    print("[Auth] OTP endpoint registered ✓")
    print("[Analytics] Data endpoint registered at POST /auth/analytics-data ✓")
    print("[Analytics] Dashboard middleware registered at GET/POST /auth/analytics ✓")
    print("[Profile] Profile page registered at GET/POST /profile ✓")
except Exception as e:
    print(f"[Auth] OTP endpoint not available: {e}")

# ─────────────────────────────────────────────
# 8. AUTH — Chainlit native login with OTP
# ─────────────────────────────────────────────
@cl.password_auth_callback
def auth_callback(username: str, password: str):
    loop = asyncio.get_event_loop()
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
# 9. DADI IMAGE PICKER
# ─────────────────────────────────────────────
_DADI_IMAGES = {
    "karate":   "public/images/dadi_karate.png",
    "smirk":    "public/images/dadi kicking with smirk.png",
    "dancing":  "public/images/dadi_dancing.png",
    "dancing_smirk": "public/images/dadi_dancing_with_smirk.png",
    "flowers":  "public/images/dadi picking flowers.png",
    "reading":  "public/images/dadi reading book.png",
    "tea":      "public/images/dadi tea.png",
    "default":  "public/images/dadi.png",
}

def _pick_dadi_image(user_text: str, reply: str) -> str:
    """Return the path to the most contextually appropriate Dadi image."""
    combined = (user_text + " " + reply).lower()

    # Scolding / fighting mood
    if any(w in combined for w in [
        "scold", "roast", "shame", "karate", "kick", "fight", "slap",
        "how dare", "behave", "disrespect", "nonsense", "bakwaas",
        "padhai nahi", "phone band", "uthao", "lazy",
    ]):
        return _DADI_IMAGES["karate"]

    # Sarcastic / smirk mood
    if any(w in combined for w in [
        "obviously", "of course", "really?", "seriously", "wow beta",
        "achha", "haan haan", "sach mein", "please", "oh sure",
    ]):
        return _DADI_IMAGES["smirk"]

    # Celebrating / happy mood
    if any(w in combined for w in [
        "congratulations", "well done", "proud", "shaabash", "dance",
        "celebrate", "party", "excited", "yay", "win", "pass", "score",
        "wedding", "birthday", "festival",
    ]):
        return random.choice([_DADI_IMAGES["dancing"], _DADI_IMAGES["dancing_smirk"]])

    # Peaceful / garden mood
    if any(w in combined for w in [
        "flower", "garden", "nature", "walk", "fresh air", "peaceful",
        "calm", "slow down", "morning", "stress", "breathe",
    ]):
        return _DADI_IMAGES["flowers"]

    # Wisdom / advice mood
    if any(w in combined for w in [
        "advice", "wisdom", "read", "book", "learn", "study", "knowledge",
        "career", "future", "goal", "life lesson", "think",
    ]):
        return _DADI_IMAGES["reading"]

    # Chai / relaxed chat
    if any(w in combined for w in [
        "chai", "tea", "sit", "relax", "rest", "baat", "baito", "aaо",
        "tell me", "sun", "suno", "kya hua",
    ]):
        return _DADI_IMAGES["tea"]

    # Fallback: rotate through calm images
    return random.choice([
        _DADI_IMAGES["default"],
        _DADI_IMAGES["tea"],
        _DADI_IMAGES["reading"],
        _DADI_IMAGES["flowers"],
    ])

# ─────────────────────────────────────────────
# 9b. SHARE CARD GENERATOR
# ─────────────────────────────────────────────
_SHARE_CARDS: dict[str, bytes] = {}  # in-memory cache
_SUPA_CARDS_BUCKET = "share-cards"

async def _save_card(card_id: str, png: bytes) -> None:
    _SHARE_CARDS[card_id] = png
    try:
        async with httpx.AsyncClient() as client:
            r = await client.put(
                f"{SUPABASE_URL}/storage/v1/object/{_SUPA_CARDS_BUCKET}/{card_id}.png",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "image/png",
                    "x-upsert": "true",
                },
                content=png,
                timeout=15,
            )
        if r.status_code not in (200, 201):
            print(f"[Share] Supabase upload failed: {r.status_code} {r.text}")
    except Exception as e:
        print(f"[Share] Supabase upload error: {e}")

async def _load_card(card_id: str) -> bytes | None:
    if card_id in _SHARE_CARDS:
        return _SHARE_CARDS[card_id]
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{SUPABASE_URL}/storage/v1/object/{_SUPA_CARDS_BUCKET}/{card_id}.png",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                },
                timeout=10,
            )
        if r.status_code == 200:
            _SHARE_CARDS[card_id] = r.content
            return r.content
        return None
    except Exception as e:
        print(f"[Share] Supabase fetch error: {e}")
        return None

def _try_font(size: int):
    """Load best available font for the deployment environment."""
    from PIL import ImageFont
    for path in [
        "public/fonts/Kalam-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "C:/Windows/Fonts/georgia.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()

def _generate_share_card(dadi_text: str, user_text: str = "") -> bytes:
    """Generate a share card matching the client-side canvas style:
    white left panel with Dadi image, cream right panel with chat bubbles."""
    from PIL import Image, ImageDraw

    # ── Colours matching the JS canvas ──────────────────────────────────────
    WHITE  = (255, 255, 255)
    CREAM  = (242, 237, 232)   # #F2EDE8
    RED    = (139, 26, 26)     # #8B1A1A
    ORANGE = (255, 77, 0)      # #FF4D00
    DARK   = (45, 26, 16)      # #2d1a10
    TAN    = (158, 122, 90)    # #9e7a5a

    W  = 1080
    LW = 360        # left panel width
    PAD = 56
    BPX, BPY = 30, 22
    BW = W - LW - PAD * 2     # bubble width

    # ── Clean text ────────────────────────────────────────────────────────────
    def _clean(t):
        t = re.sub(r'\*\*[^*]+\*\*\n\n', '', t)
        t = re.sub(r'\*\*|\*|#{1,3}\s?', '', t).strip()
        return t

    dadi_clean = _clean(dadi_text)
    user_clean = _clean(user_text)[:200] if user_text else ""

    # ── Fonts ─────────────────────────────────────────────────────────────────
    f_brand  = _try_font(30)   # "MYDADI.IN" bottom-left
    f_header = _try_font(22)   # "DADI AI" top-right
    f_label  = _try_font(19)   # "You" / "Dadi 👵🏾" labels
    f_user   = _try_font(24)   # user bubble text
    f_dadi   = _try_font(28)   # dadi bubble text (may shrink)

    # ── Pre-measure heights ───────────────────────────────────────────────────
    def wrap(text, font, max_w, draw_dummy):
        words = text.split()
        lines, line = [], ""
        for w in words:
            test = (line + " " + w).strip()
            if draw_dummy.textlength(test, font=font) > max_w and line:
                lines.append(line); line = w
            else:
                line = test
        if line:
            lines.append(line)
        return lines

    # We need a dummy draw to measure
    dummy_img  = Image.new("RGB", (W, 100))
    dummy_draw = ImageDraw.Draw(dummy_img)

    # User bubble
    u_lines, u_bh = [], 0
    if user_clean:
        u_lines = wrap(user_clean, f_user, BW - BPX * 2, dummy_draw)[:3]
        u_fs, u_lh = 24, 36
        u_bh = BPY + u_fs + (len(u_lines) - 1) * u_lh + BPY + 26 + 36  # includes label + gap

    # Dadi bubble — shrink font if text is very long
    d_fs = 28
    while d_fs >= 14:
        f_dadi = _try_font(d_fs)
        d_lines = wrap(dadi_clean, f_dadi, BW - BPX * 2, dummy_draw)
        d_lh = round(d_fs * 1.55)
        d_bh = BPY + d_fs + (len(d_lines) - 1) * d_lh + BPY
        needed = 106 + u_bh + 26 + d_bh + 40 + 70 + 60
        if needed <= 4000:
            break
        d_fs -= 2

    H = max(1350, 106 + u_bh + 26 + d_bh + 40 + 70 + 60)

    # ── Build canvas ─────────────────────────────────────────────────────────
    img  = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(img)

    # Left panel (white — already white background)
    # Right panel (cream)
    draw.rectangle([LW, 0, W, H], fill=CREAM)

    # ── Dadi image in left panel ─────────────────────────────────────────────
    _card_images = [
        "public/images/dadi.png",
        "public/images/dadi_dancing.png",
        "public/images/dadi_karate.png",
        "public/images/dadi_dancing_with_smirk.png",
    ]
    for img_path in _card_images:
        try:
            dadi_img = Image.open(img_path).convert("RGBA")
            max_w, max_h = LW - 40, H - 100
            scale = min(max_w / dadi_img.width, max_h / dadi_img.height)
            dw, dh = int(dadi_img.width * scale), int(dadi_img.height * scale)
            dadi_img = dadi_img.resize((dw, dh), Image.LANCZOS)
            x = (LW - dw) // 2
            y = (H - dh) // 2 - 30
            img.paste(dadi_img, (x, y), dadi_img)
            break
        except Exception:
            continue

    # "MYDADI.IN" brand bottom-left in orange
    draw.text((LW // 2, H - 40), "MYDADI.IN", fill=ORANGE, font=f_brand, anchor="mm")

    # ── Right panel content ───────────────────────────────────────────────────
    RX  = LW + PAD
    RMAX = W - PAD

    # "DADI AI" header top-centre of right panel
    draw.text((LW + (W - LW) // 2, 72), "DADI AI", fill=RED, font=f_header, anchor="mm")

    cur_y = 106

    # ── User bubble (white, right-aligned) ───────────────────────────────────
    if user_clean and u_lines:
        draw.text((RMAX, cur_y), "You", fill=TAN, font=f_label, anchor="ra")
        cur_y += 26
        u_fs, u_lh = 24, 36
        u_bx = RMAX - BW
        u_bh_inner = BPY + u_fs + (len(u_lines) - 1) * u_lh + BPY
        # Bubble
        draw.rounded_rectangle([u_bx, cur_y, u_bx + BW, cur_y + u_bh_inner], radius=18, fill=WHITE)
        # Tail bottom-right
        draw.polygon([
            (RMAX - 18, cur_y + u_bh_inner),
            (RMAX + 10, cur_y + u_bh_inner + 16),
            (RMAX - 46, cur_y + u_bh_inner),
        ], fill=WHITE)
        # Text
        for i, line in enumerate(u_lines):
            draw.text((u_bx + BPX, cur_y + BPY + u_fs + i * u_lh), line, fill=DARK, font=f_user, anchor="la")
        cur_y += u_bh_inner + 36

    # ── Dadi bubble (red, left-aligned) ──────────────────────────────────────
    draw.text((RX, cur_y), "Dadi 👵🏾", fill=TAN, font=f_label, anchor="la")
    cur_y += 26
    # Bubble
    draw.rounded_rectangle([RX, cur_y, RX + BW, cur_y + d_bh], radius=18, fill=RED)
    # Tail bottom-left
    draw.polygon([
        (RX + 18, cur_y + d_bh),
        (RX - 10, cur_y + d_bh + 16),
        (RX + 46, cur_y + d_bh),
    ], fill=RED)
    # Text (white)
    for i, line in enumerate(d_lines):
        draw.text((RX + BPX, cur_y + BPY + d_fs + i * d_lh), line, fill=WHITE, font=f_dadi, anchor="la")

    # Footer "MYDADI.IN" bottom-right
    f_footer = _try_font(22)
    draw.text((RMAX, H - 70), "MYDADI.IN", fill=ORANGE, font=f_footer, anchor="ra")

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()

@cl.set_starters
async def set_starters():
    return [
        cl.Starter(label=label, message=message)
        for label, message in random.choice(STARTER_SETS)
    ]


# ─────────────────────────────────────────────
# 10. CHAINLIT HANDLERS
# ─────────────────────────────────────────────
@cl.on_chat_start
async def on_start():
    # Start daily scheduler once
    if not _scheduler.running:
        _scheduler.add_job(_run_daily_dadi_emails, "cron", hour=1, minute=30)  # 7 AM IST
        _scheduler.start()
        print("[Scheduler] Daily Dadi emails scheduled at 07:00 IST ✓")

    cl.user_session.set("messages", [])
    cl.user_session.set("response_count", 0)
    cl.user_session.set("story_chapters", [])
    cl.user_session.set("story_chapter_idx", 0)

    user = cl.context.session.user
    is_guest = user.metadata.get("role") == "guest"
    email = None if is_guest else user.identifier
    memories = await _get_memories(email) if email else []
    cl.user_session.set("email", email)
    cl.user_session.set("is_guest", is_guest)
    cl.user_session.set("memories", memories)
    cl.user_session.set("session_started_at", datetime.now(timezone.utc))

    is_first_time = not is_guest and len(memories) == 0
    cl.user_session.set("is_first_time", is_first_time)

    await analytics.log_session_start(
        session_id=cl.context.session.id,
        user_email=email,
        user_type="guest" if is_guest else "registered",
        memory_count=len(memories),
    )

    if is_first_time:
        await cl.Message(
            content=(
                "Arre, naaya chehra! 👀 Aaja beta, baith ja.\n\n"
                "Main hoon Pushpa Devi Sharma — sab Dadi bolte hain. "
                "Bata, kya naam hai tera? Aur kya chal raha hai zindagi mein?"
            ),
            author="Dadi 👵🏾",
            actions=[
                cl.Action(
                    name="daily_optin",
                    payload={"value": "yes"},
                    label="📩 Haan Dadi, roz subah message bhejo!",
                )
            ],
        ).send()


@cl.on_chat_resume
async def on_resume(thread: dict):
    """Restore session state when user refreshes a chat with existing messages."""
    if not _scheduler.running:
        _scheduler.add_job(_run_daily_dadi_emails, "cron", hour=1, minute=30)
        _scheduler.start()

    # Rebuild conversation history from persisted thread steps
    messages = []
    for step in thread.get("steps", []):
        step_type = step.get("type", "")
        output = step.get("output", "") or ""
        if step_type == "user_message" and output:
            messages.append({"role": "user", "content": output})
        elif step_type == "assistant_message" and output:
            messages.append({"role": "assistant", "content": output})

    cl.user_session.set("messages", messages)
    cl.user_session.set("response_count", len([m for m in messages if m["role"] == "assistant"]))
    cl.user_session.set("story_chapters", [])
    cl.user_session.set("story_chapter_idx", 0)

    user = cl.context.session.user
    is_guest = user.metadata.get("role") == "guest"
    email = None if is_guest else user.identifier
    memories = await _get_memories(email) if email else []
    cl.user_session.set("email", email)
    cl.user_session.set("is_guest", is_guest)
    cl.user_session.set("memories", memories)
    cl.user_session.set("session_started_at", datetime.now(timezone.utc))
    cl.user_session.set("is_first_time", False)


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

        calendar_section = (
            "\n\n---\nCalendar context (let this colour your responses naturally — "
            "don't announce the date robotically, but reference the season, festival mood, "
            "or upcoming occasion the way a real dadi would in conversation):\n"
            + get_calendar_context()
        )

        is_first_time = cl.user_session.get("is_first_time", False)
        onboarding_addon = ONBOARDING_ADDON if is_first_time and len(messages) <= 2 else ""
        if is_first_time:
            cl.user_session.set("is_first_time", False)

        base_system = DADI_SYSTEM_PROMPT + onboarding_addon + memory_section + rag_context + search_context + cricket_context + calendar_section

        if _is_story_request(user_text):
            # ── Story mode: generate all 3 chapters in one call, deliver one at a time ──
            story_system = base_system + STORY_CHAPTER_ADDON
            llm_msgs = [SystemMessage(content=story_system)] + history_msgs + [HumanMessage(content=user_text)]

            # Collect full response (no streaming — must split before displaying)
            async def _collect_story():
                nonlocal full_reply
                async for chunk in LLM.astream(llm_msgs):
                    full_reply += chunk.content

            try:
                await asyncio.wait_for(_collect_story(), timeout=60.0)
            except asyncio.TimeoutError:
                print("[LLM] Story stream timed out")
                if not full_reply:
                    full_reply = "Arre beta, Dadi thak gayi — story baad mein sunao. Abhi dobara poocho!"

            raw_chapters = [c.strip() for c in full_reply.split("<<<CHAPTER>>>") if c.strip()]
            while len(raw_chapters) < 3:
                raw_chapters.append("")
            chapters = raw_chapters[:3]

            cl.user_session.set("story_chapters", chapters)
            cl.user_session.set("story_chapter_idx", 1)

            # Reuse msg — set content and Next Chapter action button
            msg.content = f"**📖 Kahani — Bhaag 1/3**\n\n{chapters[0]}"
            msg.actions = [cl.Action(name="next_chapter", payload={"value": "next"}, label="📖 Aage sunao, Dadi →")]

        else:
            llm_msgs = [SystemMessage(content=base_system)] + history_msgs + [HumanMessage(content=user_text)]

            async def _stream_reply():
                nonlocal full_reply
                async for chunk in LLM.astream(llm_msgs):
                    full_reply += chunk.content
                    await msg.stream_token(chunk.content)

            try:
                await asyncio.wait_for(_stream_reply(), timeout=50.0)
            except asyncio.TimeoutError:
                print("[LLM] Reply stream timed out")
                if not full_reply:
                    full_reply = "*Arre beta*, Dadi ka connection thoda slow hai. Ek baar phir poocho!"
                    await msg.stream_token(full_reply)

    except Exception as e:
        full_reply = f"*Arre!* Something went wrong beta. (Error: {e})"
        await msg.stream_token(full_reply)

    image_path = _pick_dadi_image(user_text, full_reply)
    elements = [cl.Image(path=image_path, name="dadi", display="inline")]

    msg.elements = elements

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


@cl.action_callback("next_chapter")
async def on_next_chapter(action: cl.Action):
    chapters = cl.user_session.get("story_chapters", [])
    idx = cl.user_session.get("story_chapter_idx", 1)

    if idx >= len(chapters) or not chapters[idx]:
        await cl.Message(content="Bas, yahi tha beta. Kahani khatam. 🙏", author="Dadi 👵🏾").send()
        await action.remove()
        return

    chapter_text = chapters[idx]
    chapter_num = idx + 1
    cl.user_session.set("story_chapter_idx", idx + 1)
    is_last = (idx == 2)

    if is_last:
        msg = cl.Message(
            content=f"**📖 Kahani — Bhaag {chapter_num}/3**\n\n{chapter_text}\n\n*— Aur yahi thi Dadi ki kahani. Ab ja, chai pi. 🍵*",
            author="Dadi 👵🏾",
        )
    else:
        msg = cl.Message(
            content=f"**📖 Kahani — Bhaag {chapter_num}/3**\n\n{chapter_text}",
            author="Dadi 👵🏾",
            actions=[cl.Action(name="next_chapter", payload={"value": "next"}, label="📖 Aage sunao, Dadi →")],
        )

    await msg.send()
    await action.remove()


@cl.action_callback("daily_optin")
async def on_daily_optin(action: cl.Action):
    email = cl.user_session.get("email")
    if not email:
        await cl.Message(
            content="Beta, pehle login kar — tab main roz message karungi! 😄",
            author="Dadi 👵🏾",
        ).send()
        await action.remove()
        return
    await _set_daily_optin(email, True)
    await cl.Message(
        content=(
            "Theek hai beta! Kal se roz subah 7 baje tera Dadi ka sandesh aa jayega. ☀️\n\n"
            "Aur agar kabhi band karna ho toh [profile pe aa jaana](/profile)."
        ),
        author="Dadi 👵🏾",
    ).send()
    await action.remove()


@cl.action_callback("roast_me")
async def on_roast_me(action: cl.Action):
    messages = cl.user_session.get("messages", [])
    # Build a short context so the roast is personalised
    recent_user_lines = [
        m["content"][:120] for m in messages if m["role"] == "user"
    ][-4:]
    context_hint = (
        "Based on what the user has shared: " + " | ".join(recent_user_lines)
        if recent_user_lines else ""
    )

    memories = cl.user_session.get("memories", [])
    memory_hint = (
        "Dadi also knows: " + "; ".join(memories[:5])
        if memories else ""
    )

    roast_prompt = (
        f"The user just clicked 'Roast me, Dadi!' — they are ASKING for it. "
        f"Deploy the ROAST OVERRIDE fully. Be sharp, punchy, and devastating — "
        f"but land with one line of hidden affection at the end. "
        f"{context_hint} {memory_hint}"
    )

    msg = cl.Message(content="", author="Dadi 👵🏾")
    await msg.send()
    full_roast = ""

    try:
        history_msgs = [
            HumanMessage(content=m["content"]) if m["role"] == "user" else AIMessage(content=m["content"])
            for m in messages[-6:]
        ]
        llm_msgs = [SystemMessage(content=DADI_SYSTEM_PROMPT)] + history_msgs + [HumanMessage(content=roast_prompt)]
        async for chunk in LLM.astream(llm_msgs):
            full_roast += chunk.content
            await msg.stream_token(chunk.content)
    except Exception as e:
        full_roast = "Arre beta, roast karte karte mujhe khud hi ghabrahat ho gayi. Phir aana. 😂"
        await msg.stream_token(full_roast)

    msg.elements = [cl.Image(path=_DADI_IMAGES["karate"], name="dadi", display="inline")]
    await msg.update()

    messages.append({"role": "user",      "content": "[Roast me, Dadi!]"})
    messages.append({"role": "assistant", "content": full_roast})
    cl.user_session.set("messages", messages)

    await action.remove()


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
