# 🗳️ Election Assistant — Tamil Nadu 2026

> A bilingual (Tamil + English) RAG-powered AI chatbot that helps citizens understand the Tamil Nadu Assembly Elections 2026. Built for **PromptWars Virtual — Challenge 2** by [Hack2Skill](https://hack2skill.com).

![Tech Stack](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi)
![LangChain](https://img.shields.io/badge/LangChain-0.3-1C3C3C?style=flat-square)
![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react)
![Gemini](https://img.shields.io/badge/Gemini-1.5_Flash-4285F4?style=flat-square&logo=google)
![ChromaDB](https://img.shields.io/badge/ChromaDB-0.5-orange?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## 📌 What It Does

Citizens can ask natural language questions about the Tamil Nadu 2026 elections and get **grounded, verified answers** — no hallucination, no political bias.

- **When is polling day?** → April 23, 2026
- **How do I register to vote?** → Step-by-step Form 6 guide
- **My name isn't on the list — what do I do?** → 1950 helpline + BLO process
- **யாரை வாக்களிக்கலாம்?** → Full Tamil support

Every answer cites its source and flags low-confidence responses so users always know when to verify with official channels.

---

## ✨ Features

- **RAG pipeline** — LangChain + ChromaDB with MMR retrieval, grounded on official ECI documents
- **Bilingual** — Full Tamil/English toggle; the assistant responds in the language you ask in
- **Multi-turn conversation** — Session memory with 6-exchange window
- **Low-confidence detection** — Falls back to the 1950 helpline instead of guessing
- **Non-partisan by design** — System prompt hard-coded to never predict results or endorse candidates
- **Document ingestion API** — Drop new PDFs into `/data/` and rebuild the vector store at runtime
- **Election timeline** — Live sidebar showing all 5 key milestones with done/current/future states
- **Quick questions** — Pre-built chips for the most common voter queries (in both languages)
- **Constituency Explorer** — Search and view details for top Tamil Nadu constituencies, with one-click questions to the AI assistant
- **Voter Readiness Checklist** — Interactive, bilingual 8-step checklist with a progress bar to ensure voters are election-ready
- **EVM Demo** — Realistic Electronic Voting Machine simulator with working Ballot Unit and VVPAT animation

---

## 🏗️ Architecture

```
User Question (EN/TA)
       │
       ▼
  React Frontend (Vite)
       │  POST /ask
       ▼
  FastAPI Backend
       │
       ├── Session Memory (ConversationBufferWindowMemory, k=6)
       │
       ▼
  LangChain ConversationalRetrievalChain
       │
       ├── ChromaDB Vector Store  ◄── Official ECI Documents (.txt / .pdf)
       │     └── MMR Retrieval (k=5, fetch_k=10)
       │
       ├── Google Embeddings (models/embedding-001)
       │
       └── Gemini 1.5 Flash (temp=0.1)
              │
              ▼
         Grounded Answer + Sources + Confidence Flag
```

---

## 🗂️ Project Structure

```
election-assistant/
│
├── election-assistant-backend/
│   ├── main.py                     # FastAPI app + all endpoints
│   ├── requirements.txt
│   ├── .env.example
│   ├── rag/
│   │   ├── __init__.py
│   │   └── pipeline.py             # RAG core: load → chunk → embed → retrieve → answer
│   └── data/
│       └── tn_election_2026.txt    # Pre-built knowledge base (ECI data, forms, timelines)
│
└── election-frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js              # Dev proxy → :8000
    └── src/
        ├── App.jsx                 # State, chat logic, layout
        ├── index.css               # Design system (navy + saffron + cream)
        ├── main.jsx
        ├── components/
        │   ├── Sidebar.jsx         # Language toggle, quick Qs, timeline
        │   ├── MessageBubble.jsx   # Chat bubbles + source chips
        │   ├── ConstituencyExplorer.jsx # Constituency search and data cards
        │   ├── VoterChecklist.jsx  # Interactive readiness checklist
        │   └── EVMDemo.jsx         # Interactive EVM & VVPAT simulator
        └── utils/
            ├── api.js              # askQuestion, checkHealth, clearSession
            └── i18n.js             # EN + TA strings + timeline data
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- A free Gemini API key → [aistudio.google.com](https://aistudio.google.com/app/apikey)

### 1. Clone the repo

```bash
git clone https://github.com/Dhivyess/Election_process_educator.git
cd election-assistant
```

### 2. Backend setup

```bash
cd election-assistant-backend

# Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set your API key
cp .env.example .env
# Edit .env and add: GEMINI_API_KEY=your_key_here

# Start the server
uvicorn main:app --reload --port 8000
```

The backend will automatically build the ChromaDB vector store from `/data/` on first run. Subsequent starts load the persisted store (faster).

### 3. Frontend setup

```bash
cd election-frontend

npm install
npm run dev
# Open http://localhost:3000
```

### 4. Verify everything works

```bash
curl http://localhost:8000/health
# → {"status":"ok","vector_store_docs":42,"sessions_active":0}
```

---

## 📡 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check + vector store stats |
| `POST` | `/ask` | Ask a question (main chat endpoint) |
| `POST` | `/ingest` | Upload a new PDF or TXT document |
| `POST` | `/rebuild` | Re-index all documents in `/data/` |
| `GET` | `/session/{id}` | Get conversation history |
| `DELETE` | `/session/{id}` | Clear a session |

Interactive API docs available at `http://localhost:8000/docs`

### Example — Ask a question

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "When is the polling date for Tamil Nadu 2026?",
    "language": "en"
  }'
```

```json
{
  "answer": "The polling date for Tamil Nadu Assembly Elections 2026 is April 23, 2026...",
  "session_id": "abc123-...",
  "sources": ["tn_election_2026.txt"],
  "low_confidence": false
}
```

### Example — Tamil query

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "வாக்குப்பதிவு நேரம் என்ன?",
    "session_id": "abc123",
    "language": "ta"
  }'
```

### Example — Add a new document

```bash
# Upload
curl -X POST http://localhost:8000/ingest \
  -F "file=@eci_faq.pdf"

# Re-index
curl -X POST http://localhost:8000/rebuild
```

---

## 🗃️ Adding Knowledge Base Documents

Drop any `.pdf` or `.txt` file into `election-assistant-backend/data/`, then rebuild the vector store.

Recommended documents to add:

| Document | Source | Why |
|----------|--------|-----|
| ECI Voter FAQ | [eci.gov.in](https://www.eci.gov.in/Documents/Final-ER-FAQ.pdf) | Official answers to 100+ common questions |
| TN CEO Notifications | [elections.tn.gov.in](https://www.elections.tn.gov.in) | State-specific orders and timelines |
| Form 6/7/8 Guide | ECI portal | Detailed voter registration procedures |
| MCC Handbook | ECI website | Model Code of Conduct explained |

---

## 🎨 Design System

The frontend uses a custom editorial civic palette:

| Token | Value | Usage |
|-------|-------|-------|
| `--navy` | `#0f1f3d` | Primary backgrounds, user bubbles |
| `--saffron` | `#e8620a` | Accents, active states, send button hover |
| `--cream` | `#faf6ef` | Page background |
| `--gold` | `#c9922b` | Low-confidence warning border |

Fonts: **Playfair Display** (headings) · **DM Sans** (body) · **Noto Sans Tamil** (Tamil text)

---

## 🔑 Key Technical Decisions

**MMR over standard similarity search** — Maximal Marginal Relevance fetches 10 candidates and returns the top 5 most diverse chunks, preventing repetitive context from dominating the answer.

**Temperature 0.1** — Near-deterministic output for factual, civic queries. Creative variance is undesirable when answering "what documents do I need to vote."

**ConversationBufferWindowMemory (k=6)** — Retains the last 6 exchanges per session. Prevents context window bloat while maintaining coherent follow-up question handling.

**Chunk size 800, overlap 150** — Tuned for Q&A on procedural/legal text. Large enough to preserve full procedural steps; overlap prevents mid-sentence cuts.

**Hard-coded neutrality rules** — The system prompt contains strict instructions the LLM cannot override: never predict results, never endorse candidates, never speculate beyond retrieved context.

---

## 🏆 Built For

**PromptWars Virtual** — Challenge 2  
Organized by **Hack2Skill (H2S)**  
Challenge: *"Create an assistant that helps users understand the election process, timelines, and steps in an interactive and easy-to-follow way."*

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgements

- [Election Commission of India](https://www.eci.gov.in) — official data source
- [Chief Electoral Officer, Tamil Nadu](https://www.elections.tn.gov.in)
- [LangChain](https://langchain.com) · [ChromaDB](https://www.trychroma.com) · [Google Gemini](https://deepmind.google/technologies/gemini/)
- [Hack2Skill](https://hack2skill.com) for the PromptWars challenge

---

<p align="center">Made with ❤️ for Tamil Nadu voters · Not affiliated with the Election Commission of India</p>
