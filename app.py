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
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
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
    raise EnvironmentError(f"❌ Missing env vars: {', '.join(missing)}")

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
EMBEDDINGS = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

LLM = ChatGroq(
    model="llama-3.1-8b-instant",
    api_key=GROQ_API_KEY,
    temperature=0.8,
    streaming=True,
)

# ─────────────────────────────────────────────
# 5. DIRECT SUPABASE REST HELPERS
#    Bypasses SupabaseVectorStore entirely to avoid
#    the 'params' attribute bug in newer supabase-py
# ─────────────────────────────────────────────
SUPA_HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
}

def _has_knowledge() -> bool:
    """Check if dadi_knowledge table has any rows."""
    try:
        url = f"{SUPABASE_URL}/rest/v1/dadi_knowledge?select=content&limit=1"
        r = httpx.get(url, headers=SUPA_HEADERS, timeout=10)
        return bool(r.json())
    except Exception as e:
        print(f"[RAG] Table check failed: {e}")
        return False


def _upload_chunks(chunks: list) -> bool:
    """Insert document chunks with embeddings via REST."""
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
    """Call the match_dadi_knowledge RPC function directly via REST."""
    embedding = EMBEDDINGS.embed_query(query)
    url = f"{SUPABASE_URL}/rest/v1/rpc/match_dadi_knowledge"
    payload = {
        "query_embedding": embedding,
        "match_count":     k,
        "filter":          {},
    }
    r = httpx.post(url, headers=SUPA_HEADERS, json=payload, timeout=15)
    if r.status_code != 200:
        print(f"[RAG] Retrieval failed: {r.text}")
        return []

    results = r.json()
    return [Document(page_content=row["content"], metadata=row.get("metadata", {})) for row in results]


# ─────────────────────────────────────────────
# 6. BUILD RAG CHAIN
# ─────────────────────────────────────────────
RAG_CHAIN = None

def build_rag_chain():
    global RAG_CHAIN
    if RAG_CHAIN is not None:
        return RAG_CHAIN

    try:
        if not _has_knowledge():
            pdf_path = "dadi_knowledge.pdf"
            if not os.path.exists(pdf_path):
                print("[RAG] No PDF found — falling back to plain LLM.")
                return None

            print("[RAG] Uploading PDF to Supabase...")
            loader = PyPDFLoader(pdf_path)
            docs   = loader.load()
            chunks = RecursiveCharacterTextSplitter(
                chunk_size=1000, chunk_overlap=200
            ).split_documents(docs)

            success = _upload_chunks(chunks)
            if not success:
                print("[RAG] Upload failed — falling back to plain LLM.")
                return None
            print(f"[RAG] Uploaded {len(chunks)} chunks ✓")
        else:
            print("[RAG] Knowledge already in Supabase ✓")

        # Build LCEL chain with our custom retriever
        prompt = ChatPromptTemplate.from_messages([
            ("system", DADI_SYSTEM_PROMPT + "\n\nDadi's ancient knowledge (use only if relevant):\n{context}"),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}"),
        ])

        RAG_CHAIN = (
            {
                "context": RunnableLambda(lambda x: "\n\n".join(
                    d.page_content for d in _retrieve(x["input"])
                )),
                "input":   RunnableLambda(lambda x: x["input"]),
                "history": RunnableLambda(lambda x: x["history"]),
            }
            | prompt
            | LLM
            | StrOutputParser()
        )
        print("[RAG] Chain ready ✓")
        return RAG_CHAIN

    except Exception as e:
        print(f"[RAG] Chain build failed: {e} — using plain LLM.")
        return None


print("[Startup] Building Dadi's brain...")
build_rag_chain()


# ─────────────────────────────────────────────
# 7. AUTH
# ─────────────────────────────────────────────
@cl.password_auth_callback
def auth_callback(username: str, password: str):
    if password == "dadi":
        return cl.User(identifier=username, metadata={"role": "user"})
    if password == "guest":
        guest_id = f"guest_{uuid.uuid4().hex[:8]}"
        return cl.User(identifier=guest_id, metadata={"role": "guest"})
    return None


# ─────────────────────────────────────────────
# 8. CHAINLIT HANDLERS
# ─────────────────────────────────────────────
@cl.on_chat_start
async def on_start():
    cl.user_session.set("messages", [])
    user = cl.user_session.get("user")
    is_guest = user and user.metadata.get("role") == "guest"

    greeting = (
        "*Arre beta!* 👵🏾 Finally you remembered your Dadi exists, haan?\n\n"
        "Come, sit down. Put that phone away for two seconds. "
        "Tell me everything — what problem has life given you today? "
        "Dadi is here. *Chalo, bol.*"
    )
    await cl.Message(content=greeting, author="Dadi 👵🏾").send()
    cl.user_session.set("messages", [{"role": "assistant", "content": greeting}])

    if is_guest:
        await cl.Message(
            content="*(You are chatting as a guest — Dadi won't remember this conversation next time. Login to save your history.)*",
            author="Dadi 👵🏾",
        ).send()


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

        if RAG_CHAIN:
            async for token in RAG_CHAIN.astream({"input": user_text, "history": history_msgs}):
                full_reply += token
                await msg.stream_token(token)
        else:
            llm_msgs = [SystemMessage(content=DADI_SYSTEM_PROMPT)] + history_msgs
            llm_msgs.append(HumanMessage(content=user_text))

            async for chunk in LLM.astream(llm_msgs):
                full_reply += chunk.content
                await msg.stream_token(chunk.content)

    except Exception as e:
        full_reply = f"*Arre!* Something went wrong beta. (Error: {e})"
        await msg.stream_token(full_reply)

    await msg.update()

    messages.append({"role": "assistant", "content": full_reply})
    cl.user_session.set("messages", messages)