# 👵🏾 Dadi AI — Refactored Stack

> *"She will roast you. She will fix you."*

A persona-based chatbot powered by a modern, **100% free-tier** AI stack.

---

## 🆕 What Changed (Old → New)

| Layer | Old Stack | New Stack |
|---|---|---|
| **UI** | Streamlit (basic) | **Chainlit** (streaming, beautiful) |
| **LLM** | Google Gemini (free tier limited) | **Groq + Llama 3.1** (free, ultra-fast) |
| **Embeddings** | HuggingFace | HuggingFace ✅ (kept) |
| **Vector DB** | Supabase pgvector | Supabase pgvector ✅ (kept) |
| **Sessions** | Browser cookies | Chainlit user sessions |
| **Streaming** | ❌ No | ✅ Yes — token-by-token |

---

## 🗂️ Project Structure

```
dadi_ai/
├── app.py                  ← Main Chainlit app
├── requirements.txt        ← Dependencies
├── .env.example            ← Env template (copy to .env)
├── dadi_knowledge.pdf      ← Dadi's RAG knowledge base
├── public/
│   └── custom.css          ← Custom UI theme
└── .chainlit/
    └── config.toml         ← Chainlit config
```

---

## ⚡ Quick Start

### 1. Clone & Install

```bash
git clone <your-repo>
cd dadi_ai
pip install -r requirements.txt
```

### 2. Set Up Secrets

```bash
cp .env.example .env
# Edit .env with your keys
```

**Get your free API keys:**
- 🟠 **Groq**: https://console.groq.com → Create API Key (free, no CC needed)
- 🟢 **Supabase**: https://supabase.com → New Project → Settings → API

### 3. Set Up Supabase Database

Run this SQL in your Supabase SQL editor:

```sql
-- Enable pgvector
create extension if not exists vector;

-- Table for Dadi's RAG knowledge
create table dadi_knowledge (
  id bigserial primary key,
  content text,
  metadata jsonb,
  embedding vector(384)  -- 384 dims for all-MiniLM-L6-v2
);

-- Match function for semantic search
create or replace function match_dadi_knowledge(
  query_embedding vector(384),
  match_count int default 3,
  filter jsonb default '{}'
) returns table (
  id bigint,
  content text,
  metadata jsonb,
  similarity float
)
language plpgsql
as $$
begin
  return query
  select
    dadi_knowledge.id,
    dadi_knowledge.content,
    dadi_knowledge.metadata,
    1 - (dadi_knowledge.embedding <=> query_embedding) as similarity
  from dadi_knowledge
  where metadata @> filter
  order by dadi_knowledge.embedding <=> query_embedding
  limit match_count;
end;
$$;

-- Table for chat history
create table dadi_chats (
  session_id text primary key,
  user_id text,
  title text,
  messages jsonb,
  gemini_history jsonb,
  last_updated timestamptz default now()
);
```

### 4. Add Your Knowledge PDF

Place `dadi_knowledge.pdf` in the project root. On first run, Dadi will automatically upload it to Supabase. Subsequent runs skip this step.

### 5. Run!

```bash
chainlit run app.py
```

Open http://localhost:8000 — and say hi to Dadi 👵🏾

---

## 🚀 Deploy for Free

### Option A: Hugging Face Spaces (Easiest)
1. Create a new Space → SDK: **Docker**
2. Push your code
3. Add secrets in Space Settings → Repository Secrets

### Option B: Railway
1. `railway login` → `railway init` → `railway up`
2. Add env vars in Railway dashboard
3. Start command: `chainlit run app.py --host 0.0.0.0 --port $PORT`

### Option C: Render
1. New Web Service → connect your repo
2. Build command: `pip install -r requirements.txt`
3. Start command: `chainlit run app.py --host 0.0.0.0 --port 10000`

---

## 🆓 Free Tier Limits

| Service | Free Limit |
|---|---|
| **Groq** | 14,400 req/day, 500K tokens/min |
| **Supabase** | 500MB DB, 2GB bandwidth |
| **HuggingFace** | Embeddings run locally, unlimited |

Plenty for a personal or demo project! 🎉

---

## 🔧 Customization

- **Change the LLM model**: Edit `model="llama-3.1-8b-instant"` in `app.py`
  - Options: `llama-3.1-70b-versatile`, `mixtral-8x7b-32768`, `gemma2-9b-it`
- **Change Dadi's personality**: Edit `DADI_SYSTEM_PROMPT` in `app.py`
- **Change colors**: Edit CSS variables in `public/custom.css`
- **Add more PDFs**: Modify `init_dadi_brain()` to load multiple PDFs
