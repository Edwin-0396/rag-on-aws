"""RAG API: ingest documents, retrieve with embeddings, answer with an LLM."""
import hmac
import logging
import os

import chromadb
from anthropic import Anthropic
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

from app.chunking import chunk

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format='{"level":"%(levelname)s","msg":"%(message)s"}')
log = logging.getLogger("rag")

MODEL = os.getenv("LLM_MODEL", "claude-sonnet-5-5")
TOP_K = int(os.getenv("TOP_K", "4"))
API_TOKEN = os.environ["API_TOKEN"]

app = FastAPI(title="rag-on-aws")
embedder = SentenceTransformer("all-MiniLM-L6-v2")
col = chromadb.PersistentClient(path=os.getenv("CHROMA_PATH", "/data/chroma")).get_or_create_collection("docs")
llm = Anthropic(timeout=30, max_retries=2)


def require_token(authorization: str = Header(default="")) -> None:
    expected = f"Bearer {API_TOKEN}"
    if not hmac.compare_digest(authorization.encode(), expected.encode()):
        raise HTTPException(401, "Unauthorized")


class Doc(BaseModel):
    id: str = Field(min_length=1, max_length=128, pattern=r"^[\w.-]+$")
    text: str = Field(min_length=1, max_length=200_000)


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=2_000)


@app.get("/healthz")
def health():
    return {"status": "ok"}


@app.get("/readyz")
def ready():
    return {"status": "ready", "chunks": col.count()}


@app.post("/ingest", dependencies=[Depends(require_token)])
def ingest(doc: Doc):
    parts = chunk(doc.text)
    if not parts:
        raise HTTPException(422, "Document has no content")
    col.upsert(
        ids=[f"{doc.id}-{i}" for i in range(len(parts))],
        documents=parts,
        embeddings=embedder.encode(parts).tolist(),
        metadatas=[{"source": doc.id}] * len(parts),
    )
    log.info("ingested doc=%s chunks=%d", doc.id, len(parts))
    return {"chunks": len(parts)}


@app.post("/ask", dependencies=[Depends(require_token)])
def ask(q: Question):
    if col.count() == 0:
        raise HTTPException(409, "No documents ingested yet")
    res = col.query(query_embeddings=embedder.encode([q.question]).tolist(), n_results=TOP_K)
    context = "\n---\n".join(res["documents"][0])
    sources = sorted({m["source"] for m in res["metadatas"][0]})
    msg = llm.messages.create(
        model=MODEL,
        max_tokens=500,
        system="Answer only from the provided context. If the answer is not there, say you don't know.",
        messages=[{"role": "user", "content": f"<context>\n{context}\n</context>\n\nQuestion: {q.question}"}],
    )
    log.info("answered sources=%s in_tokens=%d out_tokens=%d", sources, msg.usage.input_tokens, msg.usage.output_tokens)
    return {"answer": msg.content[0].text, "sources": sources}
