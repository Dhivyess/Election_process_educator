"""
main.py
FastAPI backend for the Election Assistant.
Endpoints:
  POST /ask              — Chat with the RAG assistant (rate-limited: 15/min)
  POST /ask/stream       — Streaming chat via SSE
  POST /ingest           — Upload a new PDF/TXT (admin-key protected)
  POST /rebuild          — Rebuild vector store (admin-key protected)
  POST /feedback         — Submit thumbs-up/down on an answer
  GET  /health           — Health check
  GET  /session/{id}     — Get session history
  DELETE /session/{id}   — Clear a session
"""

import json
import os
import time
import uuid
import logging
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from langchain_classic.memory import ConversationBufferWindowMemory

from rag.pipeline import RAGPipeline

# ─── Setup ────────────────────────────────────────────────────────────────────

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

FEEDBACK_LOG = Path(__file__).parent / "feedback.jsonl"

ADMIN_KEY = os.getenv("ADMIN_API_KEY", "changeme-set-in-env")
admin_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


async def verify_admin(key: str = Depends(admin_key_header)):
    if not key or key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Forbidden — valid X-Admin-Key header required.")


# ─── Rate Limiter ─────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)

# ─── App State ────────────────────────────────────────────────────────────────

rag_pipeline: Optional[RAGPipeline] = None
# In-memory session store: { session_id: ConversationBufferWindowMemory }
# In production, replace with Redis + TTL
session_store: dict[str, ConversationBufferWindowMemory] = {}


def get_or_create_session(session_id: str) -> ConversationBufferWindowMemory:
    """Return existing memory or create a fresh one for a session (last 10 turns)."""
    if session_id not in session_store:
        session_store[session_id] = ConversationBufferWindowMemory(
            k=10,
            memory_key="chat_history",
            return_messages=True,
            output_key="answer",
        )
        logger.info(f"New session created: {session_id}")
    return session_store[session_id]


# ─── Lifespan (startup / shutdown) ────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global rag_pipeline
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not set in environment!")
        raise RuntimeError("GEMINI_API_KEY is required. Set it in your .env file.")
    logger.info("Initializing RAG pipeline...")
    rag_pipeline = RAGPipeline(api_key=api_key)
    logger.info("RAG pipeline ready.")
    yield
    logger.info("Shutting down.")


# ─── App Init ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Election Assistant API",
    description="RAG-powered assistant for Tamil Nadu Election 2026",
    version="1.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",                                                          # local dev
        "https://election-process-educator.onrender.com",                                # Render backend
        "https://election-frontend-eight.vercel.app",                                    # Vercel production alias
        "https://election-frontend-dr4prhha8-jaya-surya-hubs-projects.vercel.app",      # Vercel deployment URL
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",        # allow all vercel preview URLs via regex
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request / Response Models ────────────────────────────────────────────────

class AskRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    language: Optional[str] = "en"   # "en" or "ta"


class AskResponse(BaseModel):
    answer: str
    session_id: str
    sources: list[str]
    low_confidence: bool


class RebuildResponse(BaseModel):
    status: str
    doc_count: int


class FeedbackRequest(BaseModel):
    session_id: str
    question: str
    answer: str
    rating: int = Field(..., ge=-1, le=1)   # 1 = thumbs up, -1 = thumbs down
    comment: Optional[str] = None


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Simple health check — also confirms vector store is loaded."""
    if rag_pipeline is None or rag_pipeline.vector_store is None:
        raise HTTPException(status_code=503, detail="RAG pipeline not ready")
    doc_count = rag_pipeline.vector_store.index.ntotal
    return {
        "status": "ok",
        "vector_store_docs": doc_count,
        "sessions_active": len(session_store),
    }


@app.post("/ask", response_model=AskResponse)
@limiter.limit("15/minute")
async def ask(request: Request, body: AskRequest):
    """
    Main chat endpoint (rate-limited: 15 req/min per IP).
    Send a question, get a RAG-grounded answer back.
    Pass session_id to maintain conversation history.
    """
    if rag_pipeline is None:
        raise HTTPException(status_code=503, detail="RAG pipeline not ready")

    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    if len(question) > 1000:
        raise HTTPException(status_code=400, detail="Question too long (max 1000 characters)")

    session_id = body.session_id or str(uuid.uuid4())
    memory = get_or_create_session(session_id)

    augmented_question = question
    if body.language == "ta":
        augmented_question = f"[Please respond in Tamil] {question}"

    try:
        result = rag_pipeline.ask(augmented_question, memory)
        return AskResponse(
            answer=result["answer"],
            session_id=session_id,
            sources=result["sources"],
            low_confidence=result["low_confidence"],
        )
    except Exception as e:
        logger.error(f"Error in /ask: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.post("/ask/stream")
@limiter.limit("15/minute")
async def ask_stream(request: Request, body: AskRequest):
    """
    Streaming chat via Server-Sent Events.
    The client should listen for 'data:' chunks and a final 'data: [DONE]' event.
    """
    if rag_pipeline is None:
        raise HTTPException(status_code=503, detail="RAG pipeline not ready")

    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    session_id = body.session_id or str(uuid.uuid4())
    memory = get_or_create_session(session_id)

    augmented_question = question
    if body.language == "ta":
        augmented_question = f"[Please respond in Tamil] {question}"

    async def generate():
        # Emit session_id first so the client can capture it
        yield f"data: {json.dumps({'session_id': session_id, 'type': 'init'})}\n\n"
        full_answer = ""
        try:
            async for chunk in rag_pipeline.astream(augmented_question, memory):
                token = chunk.get("token", "")
                if token:
                    full_answer += token
                    yield f"data: {json.dumps({'token': token, 'type': 'token'})}\n\n"
            sources = chunk.get("sources", [])
            low_confidence = "I don't have verified information" in full_answer
            yield f"data: {json.dumps({'sources': sources, 'low_confidence': low_confidence, 'type': 'done'})}\n\n"
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"data: {json.dumps({'error': str(e), 'type': 'error'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/ingest", dependencies=[Depends(verify_admin)])
async def ingest_document(file: UploadFile = File(...)):
    """
    Upload a new PDF or TXT file to the knowledge base.
    Requires X-Admin-Key header.
    Note: After uploading, call /rebuild to re-index.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in [".pdf", ".txt"]:
        raise HTTPException(status_code=400, detail="Only .pdf and .txt files are supported")

    save_path = DATA_DIR / file.filename
    try:
        with open(save_path, "wb") as f:
            content = await file.read()
            f.write(content)
        logger.info(f"Document saved: {file.filename} ({len(content)} bytes)")
        return {
            "status": "uploaded",
            "filename": file.filename,
            "size_bytes": len(content),
            "message": "Call POST /rebuild to re-index the knowledge base.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.post("/rebuild", response_model=RebuildResponse, dependencies=[Depends(verify_admin)])
async def rebuild():
    """
    Rebuild the FAISS vector store from all documents in /data.
    Requires X-Admin-Key header. Call after uploading new documents via /ingest.
    """
    if rag_pipeline is None:
        raise HTTPException(status_code=503, detail="RAG pipeline not ready")
    try:
        result = rag_pipeline.rebuild_vector_store()
        return RebuildResponse(status=result["status"], doc_count=rag_pipeline.vector_store.index.ntotal)
    except Exception as e:
        logger.error(f"Rebuild failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/feedback")
async def submit_feedback(body: FeedbackRequest):
    """
    Submit a thumbs-up (rating=1) or thumbs-down (rating=-1) on an assistant answer.
    Logged to feedback.jsonl for offline analysis / fine-tuning.
    """
    entry = {
        "timestamp": time.time(),
        "session_id": body.session_id,
        "question": body.question,
        "answer": body.answer,
        "rating": body.rating,
        "comment": body.comment,
    }
    try:
        with open(FEEDBACK_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logger.info(f"Feedback logged: session={body.session_id} rating={body.rating}")
        return {"status": "recorded"}
    except Exception as e:
        logger.error(f"Failed to log feedback: {e}")
        raise HTTPException(status_code=500, detail="Could not record feedback")


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    """Retrieve conversation history for a session."""
    if session_id not in session_store:
        raise HTTPException(status_code=404, detail="Session not found")
    memory = session_store[session_id]
    messages = memory.chat_memory.messages
    history = [
        {"role": "human" if i % 2 == 0 else "assistant", "content": m.content}
        for i, m in enumerate(messages)
    ]
    return {"session_id": session_id, "history": history}


@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """Clear conversation history for a session (start fresh)."""
    if session_id not in session_store:
        raise HTTPException(status_code=404, detail="Session not found")
    del session_store[session_id]
    return {"status": "cleared", "session_id": session_id}
