"""
rag/pipeline.py
Core RAG pipeline using LangChain + ChromaDB + Gemini.
Handles document ingestion and question answering in English/Tamil.
"""

import os
import time
import logging
import asyncio
from pathlib import Path
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_core.prompts import PromptTemplate
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferWindowMemory

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
8. Format your answers using Markdown where helpful: use **bold** for key terms, bullet lists for steps, and numbered lists for procedures.

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


# ─── Workaround for LangChain Embedding Rate Limits ────────────────────────

class RateLimitedEmbeddings(GoogleGenerativeAIEmbeddings):
    """
    Patch for embedding rate limits on free tier Gemini API.
    Processes embeddings sequentially with 1.5s delay between requests
    to avoid 429 (Resource Exhausted) errors.
    """
    def embed_documents(self, texts: list[str], **kwargs) -> list[list[float]]:
        """Embed multiple texts with rate limiting."""
        embeddings = []
        for i, text in enumerate(texts):
            if i > 0:
                time.sleep(1.5)  # Prevent rate limiting
            try:
                # Call superclass to avoid infinite recursion
                batch = super().embed_documents([text], **kwargs)
                embeddings.append(batch[0])
            except Exception as e:
                logger.warning(f"Failed to embed text {i}: {e}")
                embeddings.append([0.0] * 768)  # Fallback embedding
        return embeddings


# ─── RAGPipeline Class ────────────────────────────────────────────────────────

class RAGPipeline:
    """
    Manages the full RAG lifecycle:
    - Loading & chunking documents
    - Building/loading the ChromaDB vector store
    - Running conversational QA with streaming support
    """

    def __init__(self, api_key: str):
        """
        Initialize the RAG pipeline.
        
        Args:
            api_key: Google Gemini API key
        """
        self.api_key = api_key

        # Initialize embeddings with rate limiting patch
        self.embeddings = RateLimitedEmbeddings(
            model="models/text-embedding-004",
            google_api_key=api_key,
        )

        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=api_key,
            temperature=0.1,  # Low temp for factual consistency
        )
        
        self.vector_store: Optional[FAISS] = None
        self._load_or_build_vector_store()

    # ── Document Loading ──────────────────────────────────────────────────────

    def _load_documents(self) -> list:
        """
        Load all .txt and .pdf files from the data directory.
        
        Returns:
            List of loaded documents with metadata
        """
        documents = []
        if not DATA_DIR.exists():
            logger.warning(f"Data directory not found: {DATA_DIR}")
            return documents

        for file_path in DATA_DIR.iterdir():
            if file_path.is_file():
                try:
                    if file_path.suffix == ".txt":
                        loader = TextLoader(str(file_path), encoding="utf-8")
                        docs = loader.load()
                        documents.extend(docs)
                        logger.info(f"Loaded TXT: {file_path.name} ({len(docs)} pages)")
                    elif file_path.suffix == ".pdf":
                        loader = PyPDFLoader(str(file_path))
                        docs = loader.load()
                        documents.extend(docs)
                        logger.info(f"Loaded PDF: {file_path.name} ({len(docs)} pages)")
                except Exception as e:
                    logger.error(f"Failed to load {file_path.name}: {e}", exc_info=True)

        logger.info(f"Total documents loaded: {len(documents)}")
        return documents

    def _chunk_documents(self, documents: list) -> list:
        """
        Split documents into overlapping chunks for retrieval.
        
        Args:
            documents: List of loaded documents
            
        Returns:
            List of chunked documents
        """
        if not documents:
            logger.warning("No documents to chunk")
            return []
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,       # Large enough for full context
            chunk_overlap=150,    # Overlap prevents cutting mid-sentence
            separators=["\n\n", "\n", "===", "---", ". ", " "],
        )
        chunks = splitter.split_documents(documents)
        logger.info(f"Total chunks created: {len(chunks)}")
        return chunks

    # ── Vector Store ──────────────────────────────────────────────────────────

    def _load_or_build_vector_store(self):
        """
        Load existing FAISS vector store or build a fresh one from documents.
        Called automatically on initialization.
        """
        FAISS_DIR.mkdir(parents=True, exist_ok=True)

        # Check if a persisted store already exists
        if (FAISS_DIR / "index.faiss").exists():
            logger.info("Loading existing FAISS vector store...")
            try:
                self.vector_store = FAISS.load_local(
                    folder_path=str(FAISS_DIR),
                    embeddings=self.embeddings,
                    allow_dangerous_deserialization=True
                )
                doc_count = self.vector_store.index.ntotal if hasattr(self.vector_store, 'index') else 0
                logger.info(f"Vector store loaded. Collection count: {doc_count}")
            except Exception as e:
                logger.error(f"Failed to load vector store: {e}. Rebuilding...", exc_info=True)
                self._build_vector_store()
        else:
            logger.info("No existing vector store found. Building from documents...")
            self._build_vector_store()

    def _build_vector_store(self):
        """
        Ingest documents and create a new FAISS vector store.
        Persists to disk for future loads.
        """
        documents = self._load_documents()
        if not documents:
            raise RuntimeError("No documents found in /data directory. Add .txt or .pdf files.")

        chunks = self._chunk_documents(documents)
        if not chunks:
            raise RuntimeError("No chunks created from documents.")

        try:
            self.vector_store = FAISS.from_documents(
                documents=chunks,
                embedding=self.embeddings,
            )
            self.vector_store.save_local(str(FAISS_DIR))
            doc_count = self.vector_store.index.ntotal if hasattr(self.vector_store, 'index') else 0
            logger.info(f"Vector store built and persisted. Total vectors: {doc_count}")
        except Exception as e:
            logger.error(f"Failed to build vector store: {e}", exc_info=True)
            raise

    def rebuild_vector_store(self) -> dict:
        """
        Force a complete rebuild of the vector store.
        Call this after adding new documents via /ingest endpoint.
        
        Returns:
            {status: "rebuilt", doc_count: N}
        """
        import shutil
        try:
            if FAISS_DIR.exists():
                shutil.rmtree(FAISS_DIR)
                logger.info("Cleared existing FAISS DB.")
            FAISS_DIR.mkdir(parents=True, exist_ok=True)
            self._build_vector_store()
            doc_count = self.vector_store.index.ntotal if hasattr(self.vector_store, 'index') else 0
            return {"status": "rebuilt", "doc_count": doc_count}
        except Exception as e:
            logger.error(f"Rebuild failed: {e}", exc_info=True)
            raise

    # ── Conversational QA ─────────────────────────────────────────────────────

    def get_chain(self, session_memory: ConversationBufferWindowMemory) -> ConversationalRetrievalChain:
        """
        Create a conversational retrieval chain with session-scoped memory.
        
        Args:
            session_memory: ConversationBufferWindowMemory for this session
            
        Returns:
            ConversationalRetrievalChain ready to invoke
        """
        retriever = self.vector_store.as_retriever(
            search_type="mmr",            # Max Marginal Relevance — diverse results
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

    def ask(self, question: str, session_memory: ConversationBufferWindowMemory) -> dict:
        """
        Answer a question using RAG (synchronous).
        
        Args:
            question: User's question
            session_memory: Session conversation memory
            
        Returns:
            {answer, sources, low_confidence}
        """
        if not self.vector_store:
            raise RuntimeError("Vector store not initialized.")

        chain = self.get_chain(session_memory)

        try:
            result = chain.invoke({"question": question})
            answer = result.get("answer", "").strip()
            source_docs = result.get("source_documents", [])

            # Extract unique source file names
            sources = list({
                doc.metadata.get("source", "Official Election Documents").split("/")[-1].split("\\")[-1]
                for doc in source_docs
            })

            # Flag low-confidence responses
            low_confidence = "I don't have verified information" in answer

            return {
                "answer": answer,
                "sources": sources,
                "low_confidence": low_confidence,
            }

        except Exception as e:
            logger.error(f"RAG chain error: {e}", exc_info=True)
            raise

    async def astream(self, question: str, session_memory: ConversationBufferWindowMemory):
        """
        Stream answer tokens for the given question (async generator).
        
        Args:
            question: User's question
            session_memory: Session conversation memory
            
        Yields:
            Dicts during streaming: {token: "..."} then {sources: [...], low_confidence: bool}
        """
        if not self.vector_store:
            raise RuntimeError("Vector store not initialized.")

        try:
            retriever = self.vector_store.as_retriever(
                search_type="mmr",
                search_kwargs={"k": 5, "fetch_k": 10},
            )

            # Retrieve relevant docs
            docs = retriever.invoke(question)
            context = "\n\n".join(doc.page_content for doc in docs)
            chat_history = session_memory.load_memory_variables({}).get("chat_history", "")

            # Format prompt
            prompt_text = QA_PROMPT.format(
                context=context,
                chat_history=chat_history,
                question=question,
            )

            # Stream tokens from LLM
            full_answer = ""
            async for chunk in self.llm.astream(prompt_text):
                token = chunk.content if hasattr(chunk, "content") else str(chunk)
                full_answer += token
                yield {"token": token}
                await asyncio.sleep(0.01)  # Slight delay for streaming effect

            # Save to memory after streaming completes
            session_memory.save_context({"input": question}, {"answer": full_answer})

            # Extract sources and confidence
            sources = list({
                doc.metadata.get("source", "Official Election Documents").split("/")[-1].split("\\")[-1]
                for doc in docs
            })
            low_confidence = "I don't have verified information" in full_answer
            
            yield {
                "sources": sources,
                "low_confidence": low_confidence,
                "type": "done"
            }

        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            yield {"error": str(e), "type": "error"}
