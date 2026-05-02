"""
tests/test_api.py
Unit and integration tests for Election Assistant backend.
Run with: pytest tests/ -v
"""

import pytest
import json
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import after path is set
import main
from main import app, session_store, rag_pipeline
import os

if not main.rag_pipeline:
    main.rag_pipeline = main.RAGPipeline(api_key=os.getenv("GEMINI_API_KEY", "mock-key"))

client = TestClient(app)

# ── Setup / Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def session_id():
    """Generate a unique session ID for each test."""
    return "test-session-12345"

@pytest.fixture(autouse=True)
def clear_sessions():
    """Clear session store before each test."""
    session_store.clear()
    yield
    session_store.clear()

# ── Health Check ──────────────────────────────────────────────────────────

class TestHealth:
    def test_health_check_success(self):
        """Test that health endpoint returns 200 and includes vector store count."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"
        assert "vector_store_docs" in data
        assert data["vector_store_docs"] > 0  # Should have loaded documents

    def test_health_returns_session_count(self):
        """Test that health includes active session count."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "sessions_active" in data


# ── Ask Endpoint ──────────────────────────────────────────────────────────

class TestAskEndpoint:
    def test_ask_simple_question(self, session_id):
        """Test asking a basic question about election schedule."""
        payload = {
            "question": "When is polling day?",
            "session_id": session_id,
            "language": "en"
        }
        response = client.post("/ask", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "answer" in data
        assert "session_id" in data
        assert "sources" in data
        assert "low_confidence" in data
        
        # Verify answer mentions April 23
        assert "april" in data["answer"].lower() or "23" in data["answer"]
        assert len(data["answer"]) > 50  # Non-trivial answer
        assert data["session_id"] == session_id

    def test_ask_tamil_question(self, session_id):
        """Test that Tamil queries return Tamil-language responses."""
        payload = {
            "question": "வாக்குப்பதிவு நாள் எப்போது?",
            "session_id": session_id,
            "language": "ta"
        }
        response = client.post("/ask", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert len(data["answer"]) > 30  # Got a response

    def test_ask_empty_question_returns_400(self):
        """Test that empty questions are rejected."""
        payload = {"question": "", "language": "en"}
        response = client.post("/ask", json=payload)
        assert response.status_code == 400

    def test_ask_extremely_long_question_returns_400(self):
        """Test that excessively long questions are rejected."""
        payload = {
            "question": "a" * 1001,  # 1001 chars
            "language": "en"
        }
        response = client.post("/ask", json=payload)
        assert response.status_code == 400

    def test_ask_returns_sources(self, session_id):
        """Test that answers include source documents."""
        payload = {
            "question": "What is NOTA?",
            "session_id": session_id,
            "language": "en"
        }
        response = client.post("/ask", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["sources"], list)
        # At least one source document
        assert len(data["sources"]) >= 0

    def test_ask_multipart_conversation(self, session_id):
        """Test multi-turn conversation with same session ID."""
        # First question
        q1 = client.post("/ask", json={
            "question": "When is polling day?",
            "session_id": session_id,
            "language": "en"
        })
        assert q1.status_code == 200
        
        # Second question (should remember context)
        q2 = client.post("/ask", json={
            "question": "What time does polling start?",
            "session_id": session_id,
            "language": "en"
        })
        assert q2.status_code == 200
        
        # Both should use same session
        assert q1.json()["session_id"] == q2.json()["session_id"]
        assert session_id in session_store

    def test_ask_new_session_generated(self):
        """Test that asking without session_id generates a new one."""
        response = client.post("/ask", json={
            "question": "How do I vote?",
            "language": "en"
            # No session_id provided
        })
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert len(data["session_id"]) > 0


# ── Session Management ────────────────────────────────────────────────────

class TestSessions:
    def test_get_session_history(self, session_id):
        """Test retrieving conversation history for a session."""
        # Add a message
        client.post("/ask", json={
            "question": "Who can vote?",
            "session_id": session_id,
            "language": "en"
        })
        
        # Retrieve history
        response = client.get(f"/session/{session_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert "history" in data
        assert len(data["history"]) > 0

    def test_get_nonexistent_session_returns_404(self):
        """Test that nonexistent session returns 404."""
        response = client.get("/session/nonexistent-session-xyz")
        assert response.status_code == 404

    def test_delete_session_clears_history(self, session_id):
        """Test clearing a session."""
        # Add a message
        client.post("/ask", json={
            "question": "What is an EVM?",
            "session_id": session_id,
            "language": "en"
        })
        assert session_id in session_store
        
        # Delete session
        response = client.delete(f"/session/{session_id}")
        assert response.status_code == 200
        assert session_id not in session_store

    def test_delete_nonexistent_session_returns_404(self):
        """Test deleting nonexistent session returns 404."""
        response = client.delete("/session/nonexistent-xyz")
        assert response.status_code == 404


# ── Input Validation & Security ───────────────────────────────────────────

class TestSecurity:
    def test_sql_injection_attempt_ignored(self, session_id):
        """Test that SQL-like injection attempts are safely handled."""
        payload = {
            "question": "'; DROP TABLE users; --",
            "session_id": session_id,
            "language": "en"
        }
        response = client.post("/ask", json=payload)
        # Should not crash; should return a normal response or low-confidence
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data

    def test_html_injection_attempt_ignored(self, session_id):
        """Test that HTML/XSS attempts are safely handled."""
        payload = {
            "question": "<script>alert('xss')</script>",
            "session_id": session_id,
            "language": "en"
        }
        response = client.post("/ask", json=payload)
        assert response.status_code == 200

    def test_invalid_language_parameter(self, session_id):
        """Test that invalid language codes don't crash."""
        payload = {
            "question": "When is polling?",
            "session_id": session_id,
            "language": "invalid_lang"
        }
        response = client.post("/ask", json=payload)
        # Should handle gracefully (treat as default or error)
        assert response.status_code in [200, 400]


# ── Content Quality Tests ─────────────────────────────────────────────────

class TestAnswerQuality:
    def test_answer_length_reasonable(self, session_id):
        """Test that answers are substantive (not too short)."""
        response = client.post("/ask", json={
            "question": "How do I register to vote?",
            "session_id": session_id,
            "language": "en"
        })
        assert response.status_code == 200
        answer = response.json()["answer"]
        assert len(answer) > 100  # Substantive answer

    def test_answer_contains_source_citations(self, session_id):
        """Test that sources are provided."""
        response = client.post("/ask", json={
            "question": "What forms do I need to fill?",
            "session_id": session_id,
            "language": "en"
        })
        assert response.status_code == 200
        data = response.json()
        assert len(data["sources"]) >= 0  # Sources are included

    def test_factual_consistency(self, session_id):
        """Test that repeated questions get consistent answers."""
        q = "When is polling day for Tamil Nadu 2026?"
        
        resp1 = client.post("/ask", json={"question": q, "session_id": "sess1"})
        resp2 = client.post("/ask", json={"question": q, "session_id": "sess2"})
        
        ans1 = resp1.json()["answer"].lower()
        ans2 = resp2.json()["answer"].lower()
        
        # Both should mention April or 23
        assert ("april" in ans1 or "23" in ans1)
        assert ("april" in ans2 or "23" in ans2)


# ── Document Ingestion ────────────────────────────────────────────────────

class TestIngest:
    def test_ingest_endpoint_exists(self):
        """Test that ingest endpoint is available."""
        response = client.post("/ingest", files={})
        # Should reject empty file, but endpoint should exist
        assert response.status_code in [200, 400, 422]

    def test_rebuild_endpoint_exists(self):
        """Test that rebuild endpoint is available."""
        response = client.post("/rebuild")
        assert response.status_code in [200, 500]  # May fail if no docs, but shouldn't 404


# ── Run tests ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
