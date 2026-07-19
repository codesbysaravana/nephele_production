# Nephele: AI-Powered Conversational Data Analytics Platform

Sub-second latency voice AI agent with integrated Data Warehouse, ML prediction engine, and real-time analytics dashboard. Built as a flagship portfolio project demonstrating production-grade competence across AI Engineering, ML Engineering, and Data Analytics.

---

## Architecture Overview

```
                          NEPHELE PLATFORM
    ┌─────────────────────────────────────────────────────┐
    │                                                     │
    │   FRONTEND (Vanilla JS SPA)                         │
    │   ├── #/voice      → Main voice interface           │
    │   ├── #/dashboard  → Analytics + ML charts + voice  │
    │   ├── #/attendance → QR scanner                     │
    │   └── #/landing    → Entry point                    │
    │                                                     │
    └──────────────┬──────────────────┬───────────────────┘
                   │ WebSocket        │ REST
                   ▼                  ▼
    ┌──────────────────────────────────────────────────────┐
    │   BACKEND (FastAPI ASGI)                             │
    │                                                      │
    │   WebSocket Pipelines (sub-second latency)           │
    │   ├── /ws/audio           → Main voice brain         │
    │   └── /ws/dashboard-voice → Analytics voice brain    │
    │                                                      │
    │   REST Endpoints                                     │
    │   ├── /api/analytics/*    → Chart data (5 endpoints) │
    │   ├── /api/predict        → ML inference             │
    │   ├── /api/forecast       → 7-day attendance predict │
    │   ├── /api/model/metrics  → Model health             │
    │   └── /api/attendance     → QR scan CRUD             │
    │                                                      │
    │   Shared Infrastructure                              │
    │   ├── db/         → Connection pool + safe query     │
    │   ├── ai_services/→ Streaming engine + TTS           │
    │   └── ml/         → Training + inference             │
    │                                                      │
    └───────┬────────────┬────────────────┬────────────────┘
            │            │                │
            ▼            ▼                ▼
    ┌────────────┐ ┌──────────┐   ┌─────────────┐
    │ PostgreSQL │ │  SQLite  │   │  External   │
    │ Star Schema│ │  • scans │   │  • Deepgram │
    │ • dim_users│ │  • memory│   │  • OpenAI   │
    │ • fact_sales│ └──────────┘   └─────────────┘
    └────────────┘
```

---

## Data Flow Pipelines

### Voice Pipeline (Sub-Second Latency)

```
Microphone → 250ms chunks → WebSocket → Deepgram Nova-2 STT (streaming)
    → VAD silence detection (300ms) → GPT-4o (streaming + tool-calling)
        → Sentence buffer → OpenAI TTS (Opus) → WebSocket → Browser speaker
```

### Agentic Tool System

The LLM autonomously decides which tool to invoke based on what you say:

| Voice Command | Tool Called | Action |
|---|---|---|
| "What's our total revenue?" | `query_database` | Writes SQL, executes, speaks result |
| "Show me the dashboard" | `show_dashboard` | Routes browser to `#/dashboard` |
| "Take attendance" | `trigger_attendance_mode` | Routes browser to QR scanner |
| "Remember my name is Saravana" | `save_memory` | Persists fact to SQLite |
| "Will attendance drop Friday?" | `predict_attendance` | Runs XGBoost model, speaks forecast |

### Data Warehouse Pipeline (ELT)

```
raw_data.json → ingest.py → PostgreSQL (raw_transactions JSONB)
    → transform.sql (CTEs + Window Functions)
        → dim_users (RANK() spending tier)
        → fact_sales (running SUM() cumulative revenue)
            → analytics_router.py → REST JSON → Chart.js dashboard
```

### ML Pipeline (Closed-Loop)

```
QR Scans (real attendance data in SQLite)
    + Synthetic augmentation (7200 records)
        → XGBoost Classifier (train.py)
            → model.json artifact
                → /api/predict (single inference)
                → /api/forecast (7-day outlook)
                → predict_attendance voice tool
                → Dashboard forecast chart
```

---

## Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | Vanilla JS, Chart.js, html5-qrcode | SPA with hash router, charts, QR scanning |
| Backend | Python FastAPI (ASGI) | Async WebSocket + REST gateway |
| STT | Deepgram Nova-2 (WebSocket streaming) | Real-time speech-to-text with VAD |
| LLM | OpenAI GPT-4o (streaming + tools) | Conversational AI with function calling |
| TTS | OpenAI TTS-1 (Opus format) | Text-to-speech, sentence-level dispatch |
| DWH | PostgreSQL (Star Schema) | Dimensional model with CTEs, Window Functions |
| ML | XGBoost, scikit-learn, NumPy | Attendance prediction classifier |
| Local DB | SQLite | QR attendance scans + persistent agent memory |
| Pooling | psycopg_pool | Connection pool (min 2, max 10) |

---

## Project Structure

```
backend/
├── main.py                  # FastAPI app, WebSocket endpoints, shared Deepgram session
├── attendance_db.py         # OOP SQLite class for QR scan storage
├── analytics_router.py      # REST chart endpoints (revenue, customers, growth)
├── ai_services/
│   ├── openai.py            # Main voice brain (tools, memory, SQL agent)
│   ├── dashboard_brain.py   # Dashboard voice brain (analytics + ML tools)
│   ├── streaming.py         # Shared LLM streaming + TTS dispatch engine
│   └── tts.py               # OpenAI TTS wrapper
├── db/
│   ├── __init__.py          # PostgreSQL connection pool singleton
│   └── query.py             # Shared safe SQL executor (read-only guard)
├── ml/
│   ├── train.py             # XGBoost training (real + synthetic data)
│   ├── predict.py           # Lazy-loaded model inference
│   ├── router.py            # REST: /api/predict, /api/forecast
│   └── artifacts/           # model.json + metrics.json
├── dwh/
│   ├── ingest.py            # JSON → PostgreSQL raw staging
│   ├── transform.sql        # CTE + Window Function → Star Schema
│   ├── execute_sql.py       # SQL file executor
│   └── orchestrator.py      # ELT scheduler (5-min interval)
└── requirements.txt

frontend/
├── index.html               # Entry point
├── styles.css               # Obsidian Black + Sublime Blue design system
├── main.js                  # SPA router + voice page setup
├── route.js                 # Hash router registry
└── pages/
    ├── landing.js           # Video landing page
    ├── voice.js             # Main voice interface
    ├── dashboard.js         # Analytics dashboard + voice widget
    └── attendance.js        # QR code scanner
```

---

## SQL Techniques Demonstrated

| Technique | Location | Example |
|---|---|---|
| CTEs | `transform.sql` | `WITH extracted AS (SELECT ... FROM raw_transactions)` |
| Window: RANK() | `transform.sql` | `RANK() OVER (ORDER BY SUM(amount) DESC)` |
| Window: Running SUM() | `transform.sql` | `SUM(amount) OVER (ORDER BY sale_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)` |
| Window: LAG() | `analytics_router.py` | Day-over-day revenue growth percentage |
| CASE expressions | `analytics_router.py` | Customer spending tier classification |
| UPSERT | `transform.sql` | `ON CONFLICT (customer_id) DO UPDATE SET ...` |
| JSONB extraction | `transform.sql` | `raw_data->'customer'->>'name'` |

---

## Security & Production Features

- **SQL Injection Guard:** `SET TRANSACTION READ ONLY` at database level + keyword startsWith filter
- **Connection Pooling:** `psycopg_pool.ConnectionPool` (min=2, max=10) shared across all modules
- **Input Validation:** Pydantic models with `Field(ge=, le=)` constraints on all ML endpoints
- **Persistent Memory:** Agent facts survive server restarts via SQLite
- **Latency Isolation:** Dual WebSocket pipelines — dashboard voice never affects main voice latency
- **DRY Architecture:** Shared `streaming.py` engine, shared `db/query.py`, reusable `_deepgram_session()`

---

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL database (Neon, Render, or local)
- OpenAI API Key
- Deepgram API Key

### Installation

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Environment Variables

Create `backend/.env`:

```env
OPENAI_API_KEY=sk-your-key
DEEPGRAM_API_KEY=your-key
DATABASE_URL=postgresql://user:pass@host/dbname
```

### Run

```bash
# Train the ML model (one-time)
python -m ml.train

# Start the server
uvicorn main:app --reload --port 8000
```

Open `frontend/index.html` in a browser. Tap anywhere to enter the voice interface.

### Seed Data (Optional)

```bash
# Populate attendance DB with mock scans
python seed_db.py

# Run the DWH pipeline (ingests raw_data.json → Star Schema)
cd dwh && python orchestrator.py
```

---

## Deployment

| Component | Platform | Config |
|---|---|---|
| Backend | Render | Auto-detects `uvicorn main:app`, uses `DATABASE_URL` from env |
| Frontend | Vercel | `vercel.json` SPA rewrite already configured |
| Database | Neon PostgreSQL | Free tier, connection string in env |

---

## Streaming Sequence Diagram

```mermaid
sequenceDiagram
    participant User
    participant Browser
    participant FastAPI
    participant Deepgram
    participant GPT4o
    participant TTS

    User->>Browser: Speaks
    loop Every 250ms
        Browser->>FastAPI: WebSocket audio chunk
        FastAPI->>Deepgram: Proxy chunk
    end

    Note over Deepgram: VAD detects silence (300ms)
    Deepgram-->>FastAPI: Final transcript

    FastAPI->>GPT4o: Transcript + tools
    
    alt Normal response
        loop Token streaming
            GPT4o-->>FastAPI: Words streamed
            Note over FastAPI: Buffer until punctuation
            FastAPI->>TTS: Complete sentence
            TTS-->>FastAPI: Opus audio
            FastAPI-->>Browser: Audio bytes
        end
    else Tool call (e.g. query_database)
        GPT4o-->>FastAPI: tool_call(sql="SELECT...")
        FastAPI->>PostgreSQL: Execute SQL (read-only, pooled)
        PostgreSQL-->>FastAPI: Result rows
        FastAPI->>GPT4o: Synthesize answer from data
        GPT4o-->>FastAPI: Streamed answer → TTS → Audio
    end

    Browser-->>User: Nephele speaks
```

---

Built by the PeP Cloud students.
