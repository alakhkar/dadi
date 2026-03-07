import chainlit as cl
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
import os
import json
import uuid
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
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL")

missing = [k for k, v in {
    "GROQ_API_KEY": GROQ_API_KEY,
    "SUPABASE_URL": SUPABASE_URL,
    "SUPABASE_KEY": SUPABASE_KEY,
    "DATABASE_URL": DATABASE_URL,
}.items() if not v]

if missing:
    raise EnvironmentError(f"Missing env vars: {', '.join(missing)}")

# ─────────────────────────────────────────────
# 2. CHAINLIT DATA LAYER (sidebar history)
# ─────────────────────────────────────────────
@cl.data_layer
def get_data_layer():
    return SQLAlchemyDataLayer(conninfo=DATABASE_URL)

# ─────────────────────────────────────────────
# 3. EMBEDDINGS + LLM SINGLETONS
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
        payload = {
            "content":   chunk.page_content,
            "metadata":  chunk.metadata,
            "embedding": embedding,
        }
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
# 5. MEMORY HELPERS
# ─────────────────────────────────────────────
def _get_memories(user_id: str) -> list[str]:
    try:
        url = (
            f"{SUPABASE_URL}/rest/v1/user_memories"
            f"?user_id=eq.{user_id}&select=memory&order=created_at.desc&limit=20"
        )
        r = httpx.get(url, headers=SUPA_HEADERS, timeout=10)
        if r.status_code == 200:
            return [row["memory"] for row in r.json()]
    except Exception as e:
        print(f"[Memory] Failed to load: {e}")
    return []


def _save_memory(user_id: str, memory: str):
    try:
        url = f"{SUPABASE_URL}/rest/v1/user_memories"
        headers = {**SUPA_HEADERS, "Prefer": "return=minimal"}
        r = httpx.post(url, headers=headers, json={"user_id": user_id, "memory": memory}, timeout=10)
        if r.status_code not in (200, 201):
            print(f"[Memory] Save failed: {r.text}")
    except Exception as e:
        print(f"[Memory] Save error: {e}")


async def _extract_and_save_memories(user_id: str, messages: list):
    """Use LLM to extract key facts from conversation and persist them."""
    if len(messages) < 4:
        return
    convo = "\n".join(
        f"{'User' if m['role'] == 'user' else 'Dadi'}: {m['content'][:300]}"
        for m in messages[-10:]
    )
    extraction_prompt = (
        "From this conversation, extract 1-3 short, specific facts about the USER "
        "that Dadi should remember for future conversations "
        "(e.g. their name, job, city, family situation, a problem they shared, preferences).\n\n"
        "Only extract facts clearly stated by the user. "
        "Return ONLY a JSON array of strings, nothing else.\n"
        'Example: ["Name is Riya", "Works at a startup in Bangalore", "Has an exam next week"]\n'
        "If nothing worth remembering, return: []\n\n"
        f"Conversation:\n{convo}"
    )
    try:
        response = await LLM.ainvoke([HumanMessage(content=extraction_prompt)])
        text = response.content.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        facts = json.loads(text.strip())
        for fact in facts[:3]:
            if isinstance(fact, str) and len(fact) > 5:
                _save_memory(user_id, fact)
                print(f"[Memory] Saved: {fact}")
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
        loader = PyPDFLoader(pdf_path)
        docs = loader.load()
        chunks = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200
        ).split_documents(docs)
        if _upload_chunks(chunks):
            print(f"[RAG] Uploaded {len(chunks)} chunks ✓")
        else:
            print("[RAG] Upload failed.")
    except Exception as e:
        print(f"[RAG] Startup error: {e}")


print("[Startup] Building Dadi's brain...")
ensure_knowledge_uploaded()


# ─────────────────────────────────────────────
# 7. AUTH
# ─────────────────────────────────────────────
@cl.header_auth_callback
def header_auth_callback(headers: dict):
    """Auto-create a guest user so visitors land directly in chat."""
    guest_id = f"guest_{uuid.uuid4().hex[:8]}"
    return cl.User(identifier=guest_id, metadata={"role": "guest"})


@cl.oauth_callback
def oauth_callback(provider_id: str, token: str, raw_user_data: dict, default_user: cl.User):
    """Handle Google sign-in for persistent accounts."""
    if provider_id == "google":
        return cl.User(
            identifier=raw_user_data["email"],
            metadata={
                "role":     "user",
                "provider": "google",
                "name":     raw_user_data.get("name", ""),
                "picture":  raw_user_data.get("picture", ""),
            },
        )
    return default_user


# ─────────────────────────────────────────────
# 8. ACTION CALLBACKS
# ─────────────────────────────────────────────
@cl.action_callback("signup")
async def on_signup(action: cl.Action):
    await action.remove()
    await cl.Message(
        content=(
            "Beta, ek kaam kar — click here to sign in with Google:\n\n"
            "👉 **[Sign in with Google](/login)**\n\n"
            "Ek baar sign in kar lo, phir Dadi sab yaad rakhegi — "
            "tera naam, teri baatein, sab. Promise. 💛"
        ),
        author="Dadi 👵🏾",
    ).send()


@cl.action_callback("continue_guest")
async def on_continue_guest(action: cl.Action):
    await action.remove()


# ─────────────────────────────────────────────
# 9. CHAINLIT HANDLERS
# ─────────────────────────────────────────────
@cl.on_chat_start
async def on_start():
    cl.user_session.set("messages", [])
    cl.user_session.set("response_count", 0)
    cl.user_session.set("popup_shown", False)

    user = cl.user_session.get("user")
    is_guest = not user or user.metadata.get("role") == "guest"

    memories = []
    if not is_guest:
        memories = _get_memories(user.identifier)
    cl.user_session.set("memories", memories)

    if not is_guest and memories:
        first_name = (user.metadata.get("name") or "").split()[0]
        name_part = first_name if first_name else "beta"
        greeting = (
            f"*Arre, {name_part}!* Aagaye finally! Dadi yaad karti thi...\n\n"
            "Chal bata, kya chal raha hai? *Bol.*"
        )
    else:
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

        # Memories injected into system prompt
        memories = cl.user_session.get("memories", [])
        memory_section = ""
        if memories:
            memory_section = (
                "\n\n---\nWhat Dadi remembers about this person "
                "(weave naturally into conversation, don't recite all at once):\n"
                + "\n".join(f"- {m}" for m in memories)
            )

        # RAG context
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

    # Show signup nudge after 2nd response (guests only)
    user = cl.user_session.get("user")
    is_guest = not user or user.metadata.get("role") == "guest"
    response_count = cl.user_session.get("response_count", 0) + 1
    cl.user_session.set("response_count", response_count)
    popup_shown = cl.user_session.get("popup_shown", False)

    if is_guest and response_count == 2 and not popup_shown:
        cl.user_session.set("popup_shown", True)
        try:
            await cl.Message(
                content=(
                    "Dadi won't remember you next time.\n\n"
                    "Right now you're chatting as a guest — your conversations vanish when you leave. "
                    "Sign up so Dadi can remember your name, your stories, and pick up right where you left off."
                ),
                actions=[
                    cl.Action(name="signup",         value="signup",         label="Sign Up with Google", payload={"value": "signup"}),
                    cl.Action(name="continue_guest", value="continue_guest", label="Continue as Guest",   payload={"value": "continue_guest"}),
                ],
            ).send()
        except Exception as e:
            print(f"[Nudge] Failed: {e}")


@cl.on_chat_end
async def on_end():
    """Extract and save memories for signed-in users when session ends."""
    user = cl.user_session.get("user")
    if not user or user.metadata.get("role") == "guest":
        return
    messages = cl.user_session.get("messages", [])
    print(f"[Memory] Extracting memories for {user.identifier}...")
    await _extract_and_save_memories(user.identifier, messages)
