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
                f"{SUPABASE_URL}/rest/v1/otp_codes"
                f"?email=eq.{email}&code=eq.{code}&used=eq.false&expires_at=gt.{now}&select=id&limit=1",
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
                await _save_memory(email, fact)
                print(f"[Memory] Saved for {email}: {fact}")
    except Exception as e:
        print(f"[Memory] Extraction failed: {e}")

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

# ─────────────────────────────────────────────
# 7. OTP REST ENDPOINT
# ─────────────────────────────────────────────
try:
    from chainlit.server import app as _cl_app
    from fastapi import Request
    from fastapi.responses import JSONResponse

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
        return JSONResponse({"ok": True})

    print("[Auth] OTP endpoint registered ✓")
except Exception as e:
    print(f"[Auth] OTP endpoint not available: {e}")

# ─────────────────────────────────────────────
# 8. AUTH — Chainlit native login with OTP
# ─────────────────────────────────────────────
@cl.password_auth_callback
def auth_callback(username: str, password: str):
    # Guest skip
    if password == "guest":
        guest_id = username if username.startswith("guest_") else f"guest_{username}"
        return cl.User(identifier=guest_id, metadata={"role": "guest"})
    # OTP login: username = email, password = 6-digit code
    email = username.strip().lower()
    if email and "@" in email and "." in email.split("@")[-1]:
        if _verify_otp_sync(email, password.strip()):
            return cl.User(identifier=email, metadata={"role": "user"})
    return None

# ─────────────────────────────────────────────
# 9. CHAINLIT HANDLERS
# ─────────────────────────────────────────────
@cl.on_chat_start
async def on_start():
    cl.user_session.set("messages", [])
    cl.user_session.set("response_count", 0)

    user = cl.context.session.user
    is_guest = user.metadata.get("role") == "guest"
    email = None if is_guest else user.identifier
    cl.user_session.set("email", email)
    cl.user_session.set("memories", await _get_memories(email) if email else [])

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
            docs = await _retrieve(user_text)
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

    email = cl.user_session.get("email")
    response_count = cl.user_session.get("response_count", 0) + 1
    cl.user_session.set("response_count", response_count)

    if response_count % 6 == 0:
        await _extract_and_save_memories(email, messages)
        cl.user_session.set("memories", await _get_memories(email))


@cl.on_chat_end
async def on_end():
    email = cl.user_session.get("email")
    if not email:
        return
    messages = cl.user_session.get("messages", [])
    print(f"[Memory] Session ended — extracting for {email}")
    await _extract_and_save_memories(email, messages)
