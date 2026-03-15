import chainlit as cl
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
import os
import json
import uuid
import random
import string
from datetime import datetime, timezone, timedelta
from urllib.parse import unquote
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

# ─────────────────────────────────────────────
# 1. ENV / SECRETS
# ─────────────────────────────────────────────
GROQ_API_KEY   = os.environ["GROQ_API_KEY"]
SUPABASE_URL   = os.environ["SUPABASE_URL"]
SUPABASE_KEY   = os.environ["SUPABASE_KEY"]
DATABASE_URL   = os.environ["DATABASE_URL"]
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
EMAIL_FROM     = os.environ.get("EMAIL_FROM", "Dadi <onboarding@resend.dev>")

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

LLM = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=GROQ_API_KEY,
    temperature=0.8,
    streaming=True,
)

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

def _retrieve(query: str, k: int = 3) -> list[Document]:
    try:
        embedding = EMBEDDINGS.embed_query(query)
    except Exception as e:
        print(f"[RAG] Embedding failed: {e}")
        return []
    r = httpx.post(f"{SUPABASE_URL}/rest/v1/rpc/match_dadi_knowledge", headers=SUPA_HEADERS,
                   json={"query_embedding": embedding, "match_count": k, "filter": {}}, timeout=15)
    if r.status_code != 200:
        print(f"[RAG] Retrieval failed: {r.text}")
        return []
    return [Document(page_content=row["content"], metadata=row.get("metadata", {})) for row in r.json()]

# ─────────────────────────────────────────────
# 5. OTP HELPERS
# ─────────────────────────────────────────────
def _generate_otp() -> str:
    return "".join(random.choices(string.digits, k=6))

def _save_otp(email: str, code: str) -> bool:
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    r = httpx.post(f"{SUPABASE_URL}/rest/v1/otp_codes",
                   headers={**SUPA_HEADERS, "Prefer": "return=minimal"},
                   json={"email": email, "code": code, "expires_at": expires_at}, timeout=10)
    return r.status_code in (200, 201)

def _verify_otp(email: str, code: str) -> bool:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
    r = httpx.get(
        f"{SUPABASE_URL}/rest/v1/otp_codes"
        f"?email=eq.{email}&code=eq.{code}&used=eq.false&expires_at=gt.{now}&select=id&limit=1",
        headers=SUPA_HEADERS, timeout=10)
    rows = r.json() if r.status_code == 200 else []
    if not rows:
        return False
    httpx.patch(f"{SUPABASE_URL}/rest/v1/otp_codes?id=eq.{rows[0]['id']}",
                headers={**SUPA_HEADERS, "Prefer": "return=minimal"},
                json={"used": True}, timeout=10)
    return True

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
def _get_memories(email: str) -> list[str]:
    try:
        r = httpx.get(
            f"{SUPABASE_URL}/rest/v1/user_memories?user_email=eq.{email}&select=memory&order=created_at.desc&limit=20",
            headers=SUPA_HEADERS, timeout=10)
        if r.status_code == 200:
            return [row["memory"] for row in r.json()]
    except Exception as e:
        print(f"[Memory] Load failed: {e}")
    return []

def _save_memory(email: str, memory: str):
    try:
        httpx.post(f"{SUPABASE_URL}/rest/v1/user_memories",
                   headers={**SUPA_HEADERS, "Prefer": "return=minimal"},
                   json={"user_email": email, "memory": memory}, timeout=10)
    except Exception as e:
        print(f"[Memory] Save error: {e}")

async def _extract_and_save_memories(email: str, messages: list):
    if len(messages) < 4:
        return
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
    try:
        response = await LLM.ainvoke([HumanMessage(content=prompt)])
        text = response.content.strip()
        if text.startswith("```"):
            text = text.split("```")[1].lstrip("json").strip()
        facts = json.loads(text)
        for fact in facts[:3]:
            if isinstance(fact, str) and len(fact) > 5:
                _save_memory(email, fact)
                print(f"[Memory] Saved for {email}: {fact}")
    except Exception as e:
        print(f"[Memory] Extraction failed: {e}")

# ─────────────────────────────────────────────
# 7. RAG — ENSURE PDF UPLOADED ON STARTUP
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

# ─────────────────────────────────────────────
# 8. AUTH
# ─────────────────────────────────────────────
@cl.header_auth_callback
def header_auth_callback(headers: dict):
    dadi_user = None
    dadi_guest = None
    for part in headers.get("cookie", "").split(";"):
        part = part.strip()
        if part.startswith("dadi_user="):
            dadi_user = unquote(part[len("dadi_user="):])
        elif part.startswith("dadi_guest="):
            dadi_guest = part[len("dadi_guest="):]
    if dadi_user and "@" in dadi_user:
        return cl.User(identifier=dadi_user, metadata={"role": "registered"})
    guest_id = dadi_guest if dadi_guest else f"guest_{uuid.uuid4().hex[:8]}"
    return cl.User(identifier=guest_id, metadata={"role": "guest"})

# ─────────────────────────────────────────────
# 9. CHAINLIT HANDLERS
# ─────────────────────────────────────────────
@cl.on_chat_start
async def on_start():
    cl.user_session.set("messages", [])
    cl.user_session.set("response_count", 0)

    user = cl.context.session.user
    if user and user.metadata.get("role") == "registered":
        cl.user_session.set("registered_email", user.identifier)
        cl.user_session.set("popup_shown", True)
        cl.user_session.set("memories", _get_memories(user.identifier))
    else:
        cl.user_session.set("registered_email", None)
        cl.user_session.set("popup_shown", False)
        cl.user_session.set("memories", [])

    greeting = "*beta!* Finally you remembered your Dadi exists, haan?\n\nDadi is here. *Chalo, bol.*"
    await cl.Message(content=greeting, author="Dadi 👵🏾").send()
    cl.user_session.set("messages", [{"role": "assistant", "content": greeting}])


@cl.on_message
async def on_message(message: cl.Message):
    user_text = message.content
    messages = cl.user_session.get("messages", [])
    messages.append({"role": "user", "content": user_text})

    msg = cl.Message(content="", author="Dadi 👵🏾")
    await msg.send()
    full_reply = ""

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
        try:
            docs = _retrieve(user_text)
            if docs:
                rag_context = "\n\n---\nDadi's ancient knowledge (use only if relevant):\n" + "\n\n".join(d.page_content for d in docs)
        except Exception as e:
            print(f"[RAG] Retrieval error: {e}")

        llm_msgs = [SystemMessage(content=DADI_SYSTEM_PROMPT + memory_section + rag_context)] + history_msgs + [HumanMessage(content=user_text)]
        async for chunk in LLM.astream(llm_msgs):
            full_reply += chunk.content
            await msg.stream_token(chunk.content)

    except Exception as e:
        full_reply = f"*Arre!* Something went wrong beta. (Error: {e})"
        await msg.stream_token(full_reply)

    await msg.update()
    messages.append({"role": "assistant", "content": full_reply})
    cl.user_session.set("messages", messages)

    registered_email = cl.user_session.get("registered_email")
    response_count = cl.user_session.get("response_count", 0) + 1
    cl.user_session.set("response_count", response_count)

    if registered_email and response_count % 6 == 0:
        await _extract_and_save_memories(registered_email, messages)
        cl.user_session.set("memories", _get_memories(registered_email))

    # Popup nudge: after 2nd response (or on explicit signup keywords), trigger popup via hidden link
    if not registered_email:
        popup_shown = cl.user_session.get("popup_shown", False)
        signup_keywords = {"sign up", "signup", "register", "save my chat", "remember me",
                           "create account", "log in", "login", "save conversations"}
        user_wants_signup = any(kw in user_text.lower() for kw in signup_keywords)
        if (response_count == 2 and not popup_shown) or user_wants_signup:
            cl.user_session.set("popup_shown", True)
            await cl.Message(content="[](/show-login-popup)", author="Dadi 👵🏾").send()


@cl.on_chat_end
async def on_end():
    registered_email = cl.user_session.get("registered_email")
    if not registered_email:
        return
    messages = cl.user_session.get("messages", [])
    print(f"[Memory] Session ended — extracting for {registered_email}")
    await _extract_and_save_memories(registered_email, messages)


# ─────────────────────────────────────────────
# 10. REST AUTH ENDPOINTS
# Registered after all Chainlit decorators so chainlit.server.app is ready.
# ─────────────────────────────────────────────
def _register_auth_routes():
    try:
        from fastapi import Request
        from fastapi.responses import JSONResponse
        from chainlit.server import app as _app

        @_app.post("/auth/request-otp")
        async def _rest_request_otp(request: Request):
            body = await request.json()
            email = (body.get("email") or "").strip().lower()
            if not email or "@" not in email or "." not in email.split("@")[-1]:
                return JSONResponse({"ok": False, "error": "Invalid email"}, status_code=400)
            code = _generate_otp()
            if not _save_otp(email, code):
                return JSONResponse({"ok": False, "error": "Could not save OTP"}, status_code=500)
            if not await _send_otp_email(email, code):
                return JSONResponse({"ok": False, "error": "Could not send email"}, status_code=500)
            return JSONResponse({"ok": True})

        @_app.post("/auth/verify-otp")
        async def _rest_verify_otp(request: Request):
            body = await request.json()
            email = (body.get("email") or "").strip().lower()
            code  = (body.get("code")  or "").strip()
            if not email or not code:
                return JSONResponse({"ok": False, "error": "Missing fields"}, status_code=400)
            if _verify_otp(email, code):
                return JSONResponse({"ok": True})
            return JSONResponse({"ok": False, "error": "Invalid or expired code"})

        print("[Auth] REST endpoints registered: /auth/request-otp, /auth/verify-otp")
    except Exception as e:
        print(f"[Auth] WARNING: Could not register REST endpoints: {e}")

_register_auth_routes()
