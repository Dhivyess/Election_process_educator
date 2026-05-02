"""
main.py
FastAPI backend for the Election Assistant.
Endpoints:
  POST /ask                         — Chat with the RAG assistant (rate-limited: 15/min)
  POST /ask/stream                  — Streaming chat via SSE
  POST /analyze-booth-accessibility — Analyze polling booth photos (Google Vision API)
  POST /ingest                      — Upload a new PDF/TXT (admin-key protected)
  POST /rebuild                     — Rebuild vector store (admin-key protected)
  POST /feedback                    — Submit thumbs-up/down on an answer
  GET  /health                      — Health check
  GET  /session/{id}                — Get session history
  DELETE /session/{id}              — Clear a session
"""

import json
import os
import time
import uuid
import logging
import shutil
import base64
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field, validator
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from langchain.memory import ConversationBufferWindowMemory
from rag.pipeline import RAGPipeline
from rag.google_services import detect_booth_accessibility

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
    """Verify admin API key for protected endpoints."""
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
    """Initialize RAG pipeline on startup."""
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
    version="1.2.0",
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
    """Request model for /ask endpoint with validation."""
    question: str = Field(..., min_length=1, max_length=1000)
    session_id: Optional[str] = Field(None, max_length=128)
    language: Optional[str] = Field("en", pattern="^(en|ta)$")
    
    @validator('question')
    def question_must_be_clean(cls, v):
        """Remove whitespace and validate content."""
        v = v.strip()
        if not v:
            raise ValueError('Question cannot be empty')
        # Log potentially malicious patterns (but don't reject)
        dangerous_patterns = ['DROP', 'DELETE', 'INSERT', 'UPDATE', '--', '/*', '*/']
        if any(pattern in v.upper() for pattern in dangerous_patterns):
            logger.warning(f"Potentially malicious question detected: {v[:50]}")
        return v
    
    @validator('session_id')
    def session_id_format(cls, v):
        """Validate session ID format (alphanumeric, dash, underscore only)."""
        if v and not all(c.isalnum() or c in '-_' for c in v):
            raise ValueError('Invalid session ID format')
        return v


class AskResponse(BaseModel):
    """Response model for /ask endpoint."""
    answer: str
    session_id: str
    sources: list[str]
    low_confidence: bool


class RebuildResponse(BaseModel):
    """Response model for /rebuild endpoint."""
    status: str
    doc_count: int


class FeedbackRequest(BaseModel):
    """Request model for /feedback endpoint."""
    session_id: str
    question: str
    answer: str
    rating: int = Field(..., ge=-1, le=1)   # 1 = thumbs up, -1 = thumbs down, 0 = neutral
    comment: Optional[str] = None


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """
    Health check endpoint.
    Returns: status, vector store doc count, active session count.
    """
    if rag_pipeline is None or rag_pipeline.vector_store is None:
        raise HTTPException(status_code=503, detail="RAG pipeline not ready")
    doc_count = rag_pipeline.vector_store.index.ntotal if hasattr(rag_pipeline.vector_store, 'index') else 0
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
    Pass session_id to maintain conversation history across requests.
    
    Args:
        body: AskRequest with question, optional session_id and language (en/ta)
        
    Returns:
        AskResponse with answer, session_id, sources, and confidence flag
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
        logger.error(f"Error in /ask: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.post("/ask/stream")
@limiter.limit("15/minute")
async def ask_stream(request: Request, body: AskRequest):
    """
    Streaming chat via Server-Sent Events (SSE).
    
    The client should listen for 'data:' chunks with tokens, sources, and final [DONE] signal.
    Useful for real-time response streaming on the frontend.
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
        """Generate SSE events for streaming response."""
        yield f"data: {json.dumps({'session_id': session_id, 'type': 'init'})}\n\n"
        full_answer = ""
        try:
            result = rag_pipeline.ask(augmented_question, memory)
            answer = result["answer"]
            # Stream answer word by word
            for token in answer.split():
                full_answer += token + " "
                yield f"data: {json.dumps({'token': token, 'type': 'token'})}\n\n"
                await asyncio.sleep(0.01)  # Slight delay for streaming effect
            
            yield f"data: {json.dumps({'sources': result['sources'], 'low_confidence': result['low_confidence'], 'type': 'done'})}\n\n"
        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e), 'type': 'error'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/analyze-booth-accessibility")
async def analyze_booth_accessibility(file: UploadFile = File(...)):
    """
    Analyze a polling booth photo for accessibility features using Google Cloud Vision API.
    
    Detects: ramps, wheelchair spaces, accessible seating, stairs/barriers, crowding.
    Helps PwD voters find accessible polling booths.
    
    Args:
        file: Image file (JPEG, PNG)
        
    Returns:
        {
            "accessibility_score": 0-100,
            "features_detected": ["wheelchair_ramp", ...],
            "barriers_detected": ["stairs", ...],
            "recommendation": "This booth is accessible..."
        }
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are supported")
    
    try:
        content = await file.read()
        if len(content) > 5_000_000:  # 5MB limit
            raise HTTPException(status_code=413, detail="Image too large (max 5MB)")
        
        # Convert to base64 for Vision API
        image_base64 = base64.b64encode(content).decode('utf-8')
        
        # Analyze with Google Vision API
        result = detect_booth_accessibility(image_base64)
        
        logger.info(f"Booth accessibility analyzed: score={result.get('accessibility_score')}")
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Accessibility analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/ingest", dependencies=[Depends(verify_admin)])
async def ingest_document(file: UploadFile = File(...)):
    """
    Upload a new PDF or TXT file to the knowledge base.
    
    Requires X-Admin-Key header.
    Note: After uploading, call /rebuild to re-index the vector store.
    
    Args:
        file: PDF or TXT file
        
    Returns:
        Status, filename, size, and instruction to rebuild
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
        logger.error(f"Upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.post("/rebuild", response_model=RebuildResponse, dependencies=[Depends(verify_admin)])
async def rebuild():
    """
    Rebuild the ChromaDB vector store from all documents in /data.
    
    Requires X-Admin-Key header.
    Call after uploading new documents via /ingest.
    
    Returns:
        Status and new document count in the vector store
    """
    if rag_pipeline is None:
        raise HTTPException(status_code=503, detail="RAG pipeline not ready")
    try:
        result = rag_pipeline.rebuild_vector_store()
        return RebuildResponse(status=result["status"], doc_count=result.get("doc_count", 0))
    except Exception as e:
        logger.error(f"Rebuild failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/feedback")
async def submit_feedback(body: FeedbackRequest):
    """
    Submit user feedback on an assistant answer (thumbs-up/down).
    
    Logged to feedback.jsonl for offline analysis, fine-tuning, and quality metrics.
    
    Args:
        body: FeedbackRequest with session_id, question, answer, rating, optional comment
        
    Returns:
        Status: "recorded"
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
        logger.error(f"Failed to log feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not record feedback")


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    """
    Retrieve conversation history for a session.
    
    Args:
        session_id: Session ID
        
    Returns:
        {session_id, history: [{role, content}, ...]}
    """
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
    """
    Clear conversation history for a session (start fresh).
    
    Args:
        session_id: Session ID to clear
        
    Returns:
        Status: "cleared"
    """
    if session_id not in session_store:
        raise HTTPException(status_code=404, detail="Session not found")
    del session_store[session_id]
    logger.info(f"Session cleared: {session_id}")
    return {"status": "cleared", "session_id": session_id}
