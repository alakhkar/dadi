import chainlit as cl
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
import os
import json
import uuid
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
GROQ_API_KEY  = os.environ.get("GROQ_API_KEY")
SUPABASE_URL  = os.environ.get("SUPABASE_URL")
SUPABASE_KEY  = os.environ.get("SUPABASE_KEY")
DATABASE_URL  = os.environ.get("DATABASE_URL")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")        # optional — prints code if missing
EMAIL_FROM    = os.environ.get("EMAIL_FROM", "Dadi <onboarding@resend.dev>")

missing = [k for k, v in {
    "GROQ_API_KEY": GROQ_API_KEY,
    "SUPABASE_URL": SUPABASE_URL,
    "SUPABASE_KEY": SUPABASE_KEY,
    "DATABASE_URL": DATABASE_URL,
}.items() if not v]

if missing:
    raise EnvironmentError(f"Missing env vars: {', '.join(missing)}")

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
HUGGINGFACE_API_KEY = os.environ.get("HUGGINGFACEHUB_API_TOKEN")
EMBEDDINGS = HuggingFaceEndpointEmbeddings(
    model="sentence-transformers/all-MiniLM-L6-v2",
    huggingfacehub_api_token=HUGGINGFACE_API_KEY,
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
        url = f"{SUPABASE_URL}/rest/v1/dadi_knowledge?select=content&limit=1"
        r = httpx.get(url, headers=SUPA_HEADERS, timeout=10)
        return bool(r.json())
    except Exception as e:
        print(f"[RAG] Table check failed: {e}")
        return False


def _upload_chunks(chunks: list) -> bool:
    url = f"{SUPABASE_URL}/rest/v1/dadi_knowledge"
    headers = {**SUPA_HEADERS, "Prefer": "return=minimal"}
    for i, chunk in enumerate(chunks):
        embedding = EMBEDDINGS.embed_query(chunk.page_content)
        payload = {"content": chunk.page_content, "metadata": chunk.metadata, "embedding": embedding}
        r = httpx.post(url, headers=headers, json=payload, timeout=30)
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
    url = f"{SUPABASE_URL}/rest/v1/rpc/match_dadi_knowledge"
    payload = {"query_embedding": embedding, "match_count": k, "filter": {}}
    r = httpx.post(url, headers=SUPA_HEADERS, json=payload, timeout=15)
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
    url = f"{SUPABASE_URL}/rest/v1/otp_codes"
    headers = {**SUPA_HEADERS, "Prefer": "return=minimal"}
    r = httpx.post(url, headers=headers, json={"email": email, "code": code, "expires_at": expires_at}, timeout=10)
    return r.status_code in (200, 201)


def _verify_otp(email: str, code: str) -> bool:
    # Use UTC time formatted without +00:00 suffix to avoid URL encoding issues
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
    url = (
        f"{SUPABASE_URL}/rest/v1/otp_codes"
        f"?email=eq.{email}&code=eq.{code}&used=eq.false&expires_at=gt.{now}&select=id&limit=1"
    )
    r = httpx.get(url, headers=SUPA_HEADERS, timeout=10)
    rows = r.json() if r.status_code == 200 else []
    if not rows:
        return False
    # Mark as used
    otp_id = rows[0]["id"]
    httpx.patch(
        f"{SUPABASE_URL}/rest/v1/otp_codes?id=eq.{otp_id}",
        headers={**SUPA_HEADERS, "Prefer": "return=minimal"},
        json={"used": True},
        timeout=10,
    )
    return True


def _ensure_user(email: str):
    """Insert user row if not already exists."""
    url = f"{SUPABASE_URL}/rest/v1/users"
    headers = {**SUPA_HEADERS, "Prefer": "resolution=ignore-duplicates,return=minimal"}
    httpx.post(url, headers=headers, json={"email": email}, timeout=10)


async def _send_otp_email(email: str, code: str) -> bool:
    if not RESEND_API_KEY:
        print(f"[OTP] No RESEND_API_KEY — code for {email}: {code}")
        return True  # dev mode: code printed to logs
    r = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
        json={
            "from": EMAIL_FROM,
            "to":   [email],
            "subject": "Your Dadi verification code",
            "text": (
                f"Your Dadi login code is: {code}\n\n"
                "This code expires in 10 minutes.\n\n"
                "If you didn't request this, ignore this email."
            ),
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
        url = (
            f"{SUPABASE_URL}/rest/v1/user_memories"
            f"?user_email=eq.{email}&select=memory&order=created_at.desc&limit=20"
        )
        r = httpx.get(url, headers=SUPA_HEADERS, timeout=10)
        if r.status_code == 200:
            return [row["memory"] for row in r.json()]
    except Exception as e:
        print(f"[Memory] Load failed: {e}")
    return []


def _save_memory(email: str, memory: str):
    try:
        url = f"{SUPABASE_URL}/rest/v1/user_memories"
        headers = {**SUPA_HEADERS, "Prefer": "return=minimal"}
        httpx.post(url, headers=headers, json={"user_email": email, "memory": memory}, timeout=10)
    except Exception as e:
        print(f"[Memory] Save error: {e}")


async def _extract_and_save_memories(email: str, messages: list):
    """Ask LLM to extract key user facts from conversation and persist them."""
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
        loader = PyPDFLoader(pdf_path)
        docs = loader.load()
        chunks = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200).split_documents(docs)
        if _upload_chunks(chunks):
            print(f"[RAG] Uploaded {len(chunks)} chunks ✓")
    except Exception as e:
        print(f"[RAG] Startup error: {e}")


print("[Startup] Building Dadi's brain...")
ensure_knowledge_uploaded()


# ─────────────────────────────────────────────
# 8. AUTH — auto guest, no login page
# ─────────────────────────────────────────────
@cl.header_auth_callback
def header_auth_callback(headers: dict):
    guest_id = f"guest_{uuid.uuid4().hex[:8]}"
    return cl.User(identifier=guest_id, metadata={"role": "guest"})


# ─────────────────────────────────────────────
# 9. ACTION CALLBACKS
# ─────────────────────────────────────────────
@cl.action_callback("signup")
async def on_signup(action: cl.Action):
    await action.remove()

    # Step 1: ask for email
    email_res = await cl.AskUserMessage(
        content=(
            "Beta, apna email bata — Dadi wahan ek code bhejegi! "
            "(Type your email address)"
        ),
        timeout=120,
    ).send()

    if not email_res:
        await cl.Message(content="Koi baat nahi beta, jab mann kare tab aa jaana.", author="Dadi 👵🏾").send()
        return

    email = email_res["output"].strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        await cl.Message(
            content="Arre beta, ye toh sahi email nahi lagti! Dobara try karo.",
            author="Dadi 👵🏾",
        ).send()
        return

    # Step 2: generate + send OTP
    code = _generate_otp()
    if not _save_otp(email, code):
        await cl.Message(content="Kuch gadbad ho gayi beta, thodi der mein try karo.", author="Dadi 👵🏾").send()
        return

    sent = await _send_otp_email(email, code)
    if not sent:
        await cl.Message(
            content="Email nahi gayi beta. Email sahi hai? Ek baar check karo.",
            author="Dadi 👵🏾",
        ).send()
        return

    await cl.Message(
        content=f"Dadi ne `{email}` pe 6-digit code bheja! Check karo aur woh code yahan type karo.",
        author="Dadi 👵🏾",
    ).send()

    # Step 3: ask for OTP
    otp_res = await cl.AskUserMessage(
        content="Code daalo beta (6 digits):",
        timeout=300,
    ).send()

    if not otp_res:
        await cl.Message(content="Time ho gaya beta! Signup karna ho toh phir try karo.", author="Dadi 👵🏾").send()
        return

    entered = otp_res["output"].strip()

    # Step 4: verify
    if not _verify_otp(email, entered):
        await cl.Message(
            content="Galat code beta! Phir se try karo — 'Sign Up' button dobara click karo.",
            author="Dadi 👵🏾",
        ).send()
        return

    # Step 5: logged in — load memories
    _ensure_user(email)
    cl.user_session.set("registered_email", email)
    memories = _get_memories(email)
    cl.user_session.set("memories", memories)
    cl.user_session.set("popup_shown", True)  # don't show nudge again

    await cl.Message(
        content=(
            "Aa gaye beta! Dadi ne pehchaan liya. Ab sab yaad rahega — "
            "teri baatein, tera naam, sab kuch. Bol, kya chal raha hai?"
        ),
        author="Dadi 👵🏾",
    ).send()


@cl.action_callback("continue_guest")
async def on_continue_guest(action: cl.Action):
    await action.remove()


# ─────────────────────────────────────────────
# 10. CHAINLIT HANDLERS
# ─────────────────────────────────────────────
@cl.on_chat_start
async def on_start():
    cl.user_session.set("messages", [])
    cl.user_session.set("response_count", 0)
    cl.user_session.set("popup_shown", False)
    cl.user_session.set("registered_email", None)
    cl.user_session.set("memories", [])

    greeting = (
        "*beta!* Finally you remembered your Dadi exists, haan?\n\n"
        "Dadi is here. *Chalo, bol.*"
    )
    await cl.Message(content=greeting, author="Dadi 👵🏾").send()
    cl.user_session.set("messages", [{"role": "assistant", "content": greeting}])


@cl.on_message
async def on_message(message: cl.Message):
    user_text = message.content
    messages  = cl.user_session.get("messages", [])
    messages.append({"role": "user", "content": user_text})

    msg = cl.Message(content="", author="Dadi 👵🏾")
    await msg.send()

    full_reply = ""

    try:
        history_msgs = []
        for m in messages[:-1]:
            if m["role"] == "user":
                history_msgs.append(HumanMessage(content=m["content"]))
            else:
                history_msgs.append(AIMessage(content=m["content"]))

        # Build dynamic system prompt with memories + RAG
        memories = cl.user_session.get("memories", [])
        memory_section = ""
        if memories:
            memory_section = (
                "\n\n---\nWhat Dadi remembers about this person "
                "(weave naturally into conversation, don't recite all at once):\n"
                + "\n".join(f"- {m}" for m in memories)
            )

        rag_context = ""
        try:
            docs = _retrieve(user_text)
            if docs:
                rag_context = (
                    "\n\n---\nDadi's ancient knowledge (use only if relevant):\n"
                    + "\n\n".join(d.page_content for d in docs)
                )
        except Exception as e:
            print(f"[RAG] Retrieval error: {e}")

        full_system = DADI_SYSTEM_PROMPT + memory_section + rag_context
        llm_msgs = [SystemMessage(content=full_system)] + history_msgs + [HumanMessage(content=user_text)]

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

    # Periodically extract memories for logged-in users (every 6 responses)
    if registered_email and response_count % 6 == 0:
        await _extract_and_save_memories(registered_email, messages)
        # Refresh memories in session
        cl.user_session.set("memories", _get_memories(registered_email))

    # Show signup nudge after 2nd response for guests only
    popup_shown = cl.user_session.get("popup_shown", False)
    if not registered_email and response_count == 2 and not popup_shown:
        cl.user_session.set("popup_shown", True)
        try:
            await cl.Message(
                content=(
                    "Dadi won't remember you next time.\n\n"
                    "Right now you're chatting as a guest — your conversations vanish when you leave. "
                    "Sign up (just your email, no password!) so Dadi can remember your name, "
                    "your stories, and pick up right where you left off."
                ),
                actions=[
                    cl.Action(name="signup",         value="signup",         label="Sign Up — Save My Chats", payload={"value": "signup"}),
                    cl.Action(name="continue_guest", value="continue_guest", label="Continue as Guest",        payload={"value": "continue_guest"}),
                ],
            ).send()
        except Exception as e:
            print(f"[Nudge] Failed: {e}")


@cl.on_chat_end
async def on_end():
    """Save memories when session ends (best-effort)."""
    registered_email = cl.user_session.get("registered_email")
    if not registered_email:
        return
    messages = cl.user_session.get("messages", [])
    print(f"[Memory] Session ended — extracting for {registered_email}")
    await _extract_and_save_memories(registered_email, messages)
