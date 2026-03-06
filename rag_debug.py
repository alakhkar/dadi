"""
RAG Debug Script — run this to diagnose each step:
  python rag_debug.py
"""
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
}

# ── STEP 1: Check if table has data ──────────────────────
print("\n📋 STEP 1: Checking dadi_knowledge table...")
r = httpx.get(f"{SUPABASE_URL}/rest/v1/dadi_knowledge?select=content&limit=3", headers=HEADERS)
print(f"  Status: {r.status_code}")
rows = r.json()
if isinstance(rows, list) and rows:
    print(f"  ✅ Table has data! First row preview: {rows[0]['content'][:100]}...")
    print(f"  Total rows fetched (limit 3): {len(rows)}")
else:
    print(f"  ❌ Table is EMPTY or error: {rows}")
    print("  → Dadi has no knowledge uploaded yet. Delete table contents and restart app.")

# ── STEP 2: Test embedding generation ────────────────────
print("\n🧠 STEP 2: Testing embeddings...")
try:
    from langchain_huggingface import HuggingFaceEmbeddings
    emb = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    test_vec = emb.embed_query("magnetic giant Devache Gothane")
    print(f"  ✅ Embeddings working! Vector length: {len(test_vec)}")
    print(f"  First 5 values: {test_vec[:5]}")
except Exception as e:
    print(f"  ❌ Embedding failed: {e}")
    exit()

# ── STEP 3: Test RPC retrieval ────────────────────────────
print("\n🔍 STEP 3: Testing RPC match_dadi_knowledge...")
payload = {
    "query_embedding": test_vec,
    "match_count":     3,
    "filter":          {},
}
r = httpx.post(
    f"{SUPABASE_URL}/rest/v1/rpc/match_dadi_knowledge",
    headers=HEADERS,
    json=payload,
    timeout=15
)
print(f"  Status: {r.status_code}")
if r.status_code == 200:
    results = r.json()
    if results:
        print(f"  ✅ Retrieved {len(results)} chunks!")
        for i, row in enumerate(results):
            print(f"\n  --- Chunk {i+1} (similarity: {row.get('similarity', 'N/A'):.3f}) ---")
            print(f"  {row['content'][:200]}...")
    else:
        print("  ❌ RPC returned empty results — embeddings may be mismatched or table empty")
else:
    print(f"  ❌ RPC call failed: {r.text}")

# ── STEP 4: Check RAG_CHAIN is actually being used ────────
print("\n⛓️  STEP 4: Checking RAG_CHAIN in app...")
print("  Look at your terminal when you run 'chainlit run app.py'")
print("  You should see ONE of these lines:")
print("    [RAG] Knowledge already in Supabase ✓  → table has data, chain built")
print("    [RAG] Uploading PDF to Supabase...      → first run upload")
print("    [RAG] No PDF found — falling back       → dadi_knowledge.pdf missing")
print("    [RAG] Chain build failed: ...           → something else broke")
print("\n  If you see 'Chain ready ✓' but answers ignore the PDF,")
print("  the issue is in the prompt — context is retrieved but not used.")

print("\n✅ Debug complete!")