"""
rag/pipeline.py
Core RAG pipeline using LangChain + ChromaDB + Gemini.
Handles document ingestion and question answering in English/Tamil.
"""

import os
import time
import logging
from pathlib import Path
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_core.prompts import PromptTemplate

# --- Classic imports for v1.0 compatibility ---
from langchain_classic.chains import ConversationalRetrievalChain
from langchain_classic.memory import ConversationBufferMemory

logger = logging.getLogger(__name__)

# ─── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FAISS_DIR = BASE_DIR / "faiss_db"

# ─── Prompts ─────────────────────────────────────────────────────────────────

SYSTEM_PROMPT_TEMPLATE = """You are an official, non-partisan Election Assistant for the Tamil Nadu Assembly Elections 2026.
Your role is to help citizens understand the election process, timelines, voter registration, and voting procedures.

STRICT RULES YOU MUST FOLLOW:
1. Answer ONLY from the provided context. Do NOT use outside knowledge.
2. If the context does not contain the answer, say: "I don't have verified information on that. Please call the official Voter Helpline: 1950 or visit elections.tn.gov.in"
3. NEVER predict election outcomes, endorse candidates, or express political opinions.
4. Always cite which part of your information comes from (e.g., "According to ECI guidelines..." or "As per the official schedule...").
5. If the user writes in Tamil, respond in Tamil. If in English, respond in English. If mixed, respond in the language the question is primarily in.
6. Keep responses concise, clear, and accessible — avoid bureaucratic jargon.
7. For urgent issues (name not on roll, lost ID on polling day), always include the 1950 helpline.

CONTEXT FROM OFFICIAL ELECTION DOCUMENTS:
{context}

CONVERSATION HISTORY:
{chat_history}

CITIZEN'S QUESTION: {question}

YOUR RESPONSE:"""

QA_PROMPT = PromptTemplate(
    input_variables=["context", "chat_history", "question"],
    template=SYSTEM_PROMPT_TEMPLATE,
)


# ─── Workaround for LangChain Batching & Rate Limit Bugs ───────────────────────

class PatchedEmbeddings(GoogleGenerativeAIEmbeddings):
    """
    Temporary patch for the LangChain/Gemini embedding length mismatch bug.
    Forces the library to embed chunks one-by-one and adds a 1.5-second delay 
    to prevent 429 Rate Limit (Resource Exhausted) errors on free tier accounts.
    """
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        embeddings = []
        for i, text in enumerate(texts):
            # Pause for 1.5 seconds between chunks (except the first one)
            if i > 0:
                time.sleep(1.5) 
            embeddings.append(self.embed_query(text))
        return embeddings


# ─── RAGPipeline Class ────────────────────────────────────────────────────────

class RAGPipeline:
    """
    Manages the full RAG lifecycle:
    - Loading & chunking documents
    - Building/loading the ChromaDB vector store
    - Running conversational QA
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        
        # --- Using the patched class to bypass the ValueError & 429 errors ---
        self.embeddings = PatchedEmbeddings(
            model="models/gemini-embedding-2",
            google_api_key=api_key,
        )
        
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=api_key,
            temperature=0.1,          # Low temp → factual, consistent answers
        )
        self.vector_store: Optional[FAISS] = None
        self._load_or_build_vector_store()

    # ── Document Loading ──────────────────────────────────────────────────────

    def _load_documents(self) -> list:
        """Load all .txt and .pdf files from the data directory."""
        documents = []
        if not DATA_DIR.exists():
            logger.warning(f"Data directory not found: {DATA_DIR}")
            return documents

        for file_path in DATA_DIR.iterdir():
            try:
                if file_path.suffix == ".txt":
                    loader = TextLoader(str(file_path), encoding="utf-8")
                    documents.extend(loader.load())
                    logger.info(f"Loaded TXT: {file_path.name}")
                elif file_path.suffix == ".pdf":
                    loader = PyPDFLoader(str(file_path))
                    documents.extend(loader.load())
                    logger.info(f"Loaded PDF: {file_path.name}")
            except Exception as e:
                logger.error(f"Failed to load {file_path.name}: {e}")

        logger.info(f"Total documents loaded: {len(documents)}")
        return documents

    def _chunk_documents(self, documents: list) -> list:
        """Split documents into overlapping chunks for retrieval."""
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,       # Large enough for full Q&A context
            chunk_overlap=150,    # Overlap prevents cutting mid-sentence
            separators=["\n\n", "\n", "===", "---", ". ", " "],
        )
        chunks = splitter.split_documents(documents)
        logger.info(f"Total chunks created: {len(chunks)}")
        return chunks

    # ── Vector Store ──────────────────────────────────────────────────────────

    def _load_or_build_vector_store(self):
        """Load existing FAISS index or build a fresh one from documents."""
        FAISS_DIR.mkdir(parents=True, exist_ok=True)

        # Check if a persisted store already exists
        if (FAISS_DIR / "index.faiss").exists():
            logger.info("Loading existing FAISS vector store...")
            self.vector_store = FAISS.load_local(
                folder_path=str(FAISS_DIR),
                embeddings=self.embeddings,
                allow_dangerous_deserialization=True
            )
            logger.info("Vector store loaded.")
        else:
            logger.info("No existing vector store found. Building from documents...")
            self._build_vector_store()

    def _build_vector_store(self):
        """Ingest documents and create a new ChromaDB collection."""
        documents = self._load_documents()
        if not documents:
            raise RuntimeError("No documents found in /data directory. Add .txt or .pdf files.")

        chunks = self._chunk_documents(documents)

        self.vector_store = FAISS.from_documents(
            documents=chunks,
            embedding=self.embeddings,
        )
        self.vector_store.save_local(str(FAISS_DIR))
        logger.info(f"Vector store built and persisted. Total vectors: {len(chunks)}")

    def rebuild_vector_store(self):
        """Force a complete rebuild — call this after adding new documents."""
        import shutil
        if FAISS_DIR.exists():
            shutil.rmtree(FAISS_DIR)
            logger.info("Cleared existing FAISS DB.")
        FAISS_DIR.mkdir(parents=True, exist_ok=True)
        self._build_vector_store()
        return {"status": "rebuilt"}

    # ── Conversational QA ─────────────────────────────────────────────────────

    def get_chain(self, session_memory: ConversationBufferMemory) -> ConversationalRetrievalChain:
        """Create a conversational retrieval chain with session-scoped memory."""
        retriever = self.vector_store.as_retriever(
            search_type="mmr",            # Max Marginal Relevance → diverse results
            search_kwargs={"k": 5, "fetch_k": 10},
        )
        chain = ConversationalRetrievalChain.from_llm(
            llm=self.llm,
            retriever=retriever,
            memory=session_memory,
            combine_docs_chain_kwargs={"prompt": QA_PROMPT},
            return_source_documents=True,
            verbose=False,
        )
        return chain

    def ask(self, question: str, session_memory: ConversationBufferMemory) -> dict:
        """
        Answer a question using RAG.
        Returns: { answer, sources, confidence }
        """
        if not self.vector_store:
            raise RuntimeError("Vector store not initialized.")

        chain = self.get_chain(session_memory)

        try:
            result = chain.invoke({"question": question})
            answer = result.get("answer", "").strip()
            source_docs = result.get("source_documents", [])

            # Extract unique source names for transparency
            sources = list({
                doc.metadata.get("source", "Official Election Documents").split("/")[-1]
                for doc in source_docs
            })

            # Simple confidence check — if fallback phrase is in answer, flag it
            low_confidence = "I don't have verified information" in answer

            return {
                "answer": answer,
                "sources": sources,
                "low_confidence": low_confidence,
            }

        except Exception as e:
            logger.error(f"RAG chain error: {e}")
            raise