"""
main.py
FastAPI backend for the Election Assistant.
Endpoints:
  POST /ask      — Chat with the RAG assistant
  POST /ingest   — Upload a new PDF/TXT to the knowledge base
  POST /rebuild  — Rebuild vector store from all documents
  GET  /health   — Health check
  GET  /session/{id} — Get session history
  DELETE /session/{id} — Clear a session
"""

import os
import uuid
import logging
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# --- UPDATED IMPORT ---
from langchain_classic.memory import ConversationBufferMemory

from rag.pipeline import RAGPipeline

# ─── Setup ────────────────────────────────────────────────────────────────────

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# ─── App State ────────────────────────────────────────────────────────────────

rag_pipeline: Optional[RAGPipeline] = None

# In-memory session store: { session_id: ConversationBufferMemory }
# In production, replace with Redis
session_store: dict[str, ConversationBufferMemory] = {}


# --- UPDATED TYPE HINTS AND INSTANTIATION ---
def get_or_create_session(session_id: str) -> ConversationBufferMemory:
    """Return existing memory or create a fresh one for a session."""
    if session_id not in session_store:
        session_store[session_id] = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            # Note: Removed 'k=6' because standard BufferMemory keeps the whole history. 
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
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Tighten this in production
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


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Simple health check — also confirms vector store is loaded."""
    if rag_pipeline is None or rag_pipeline.vector_store is None:
        raise HTTPException(status_code=503, detail="RAG pipeline not ready")
        
    # --- BUG FIX: FAISS uses .index.ntotal to count documents, not _collection.count() ---
    doc_count = rag_pipeline.vector_store.index.ntotal 
    
    return {
        "status": "ok",
        "vector_store_docs": doc_count,
        "sessions_active": len(session_store),
    }


@app.post("/ask", response_model=AskResponse)
async def ask(body: AskRequest):
    """
    Main chat endpoint.
    Send a question, get a RAG-grounded answer back.
    Pass session_id to maintain conversation history.
    """
    if rag_pipeline is None:
        raise HTTPException(status_code=503, detail="RAG pipeline not ready")

    # Validate question
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    if len(question) > 1000:
        raise HTTPException(status_code=400, detail="Question too long (max 1000 characters)")

    # Session management
    session_id = body.session_id or str(uuid.uuid4())
    memory = get_or_create_session(session_id)

    # Add language hint to question if Tamil is requested
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


@app.post("/ingest")
async def ingest_document(file: UploadFile = File(...)):
    """
    Upload a new PDF or TXT file to the knowledge base.
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


@app.post("/rebuild", response_model=RebuildResponse)
async def rebuild():
    """
    Rebuild the ChromaDB vector store from all documents in /data.
    Call this after uploading new documents via /ingest.
    """
    if rag_pipeline is None:
        raise HTTPException(status_code=503, detail="RAG pipeline not ready")
    try:
        result = rag_pipeline.rebuild_vector_store()
        # Ensure we return a dictionary with the required keys for RebuildResponse
        return RebuildResponse(status=result["status"], doc_count=rag_pipeline.vector_store.index.ntotal)
    except Exception as e:
        logger.error(f"Rebuild failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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