"""Minimal production-style RAG API: ingest docs, retrieve with embeddings, answer with an LLM."""
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from anthropic import Anthropic
from sentence_transformers import SentenceTransformer
import chromadb

MODEL = os.getenv("LLM_MODEL", "claude-sonnet-5-5")
TOP_K = int(os.getenv("TOP_K", "4"))

app = FastAPI(title="rag-on-aws")
embedder = SentenceTransformer("all-MiniLM-L6-v2")
db = chromadb.PersistentClient(path=os.getenv("CHROMA_PATH", "/data/chroma"))
col = db.get_or_create_collection("docs")
llm = Anthropic()


class Doc(BaseModel):
    id: str
    text: str


class Question(BaseModel):
    question: str


def chunk(text: str, size: int = 800, overlap: int = 100):
    step = size - overlap
    return [text[i:i + size] for i in range(0, max(len(text), 1), step)]


@app.get("/healthz")
def health():
    return {"status": "ok", "docs": col.count()}


@app.post("/ingest")
def ingest(doc: Doc):
    parts = chunk(doc.text)
    col.upsert(
        ids=[f"{doc.id}-{i}" for i in range(len(parts))],
        documents=parts,
        embeddings=embedder.encode(parts).tolist(),
        metadatas=[{"source": doc.id}] * len(parts),
    )
    return {"chunks": len(parts)}


@app.post("/ask")
def ask(q: Question):
    if col.count() == 0:
        raise HTTPException(400, "No documents ingested yet")
    res = col.query(query_embeddings=embedder.encode([q.question]).tolist(), n_results=TOP_K)
    ctx = res["documents"][0]
    sources = sorted({m["source"] for m in res["metadatas"][0]})
    prompt = (
        "Answer using only the context. If it is not there, say you don't know.\n\n"
        + "\n---\n".join(ctx)
        + f"\n\nQuestion: {q.question}"
    )
    msg = llm.messages.create(model=MODEL, max_tokens=500, messages=[{"role": "user", "content": prompt}])
    return {"answer": msg.content[0].text, "sources": sources}
