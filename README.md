# FinSight AI 🧠💹

> **Production-grade multi-tenant Financial Decision Intelligence platform powered by a multi-agent LLM system.**

Upload your financial portfolio (PDF), ask investment questions like *"Should I hold Apple stock?"*, and receive a structured AI-generated decision report with risk score, market sentiment, and 30-day forecast — powered by RAG + multi-agent reasoning.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 14 (App Router), TypeScript strict, Tailwind CSS, NextAuth.js, Recharts |
| **Backend** | FastAPI, SQLAlchemy async, Alembic, PostgreSQL, Pydantic v2 |
| **AI Core** | LangGraph, LangChain, OpenAI GPT-4o-mini, LLaMA-3 8B via Ollama (Pro plan) |
| **RAG** | sentence-transformers/all-MiniLM-L6-v2, FAISS (dev), Pinecone (prod), Hybrid BM25+dense |
| **Queue** | Celery + Redis (async agent jobs) |
| **Billing** | Stripe (Free / Starter ₹499 / Pro ₹1999) |
| **Auth** | NextAuth.js → JWT → FastAPI middleware |
| **Monitoring** | LangSmith (LLM tracing), Sentry (errors) |
| **CI/CD** | GitHub Actions → Docker Hub → Railway |

---

## Architecture

```
User Request (POST /analyze)
       │
       ▼ <100ms response
  FastAPI + check_quota()
       │
       ▼
  Celery Task (async)
       │
       ├─ 1. Orchestrator Node (RAG retrieval)
       │         └─ FAISS/Pinecone lookup (namespace=tenant_id)
       │
       ├─ 2. Risk Analyst ────┐
       ├─ 3. Sentiment Agent ─┤ (parallel fan-out)
       └─ 4. Forecast Agent ──┘
                 │
                 ▼
       5. Report Generator → decision_report → Redis (TTL 1hr)
                 │
                 ▼
         Frontend polls GET /jobs/{id}/status every 2s
```

### Multi-Agent LangGraph Pipeline

| Node | Model | Temperature | Output |
|------|-------|-------------|--------|
| Orchestrator | — | — | retrieved_docs |
| Risk Analyst | GPT-4o-mini | 0 | risk_score (0-1), risk_summary |
| Sentiment Agent | GPT-4o-mini | 0 | bullish/bearish/neutral + confidence |
| Forecast Agent | GPT-4o-mini (free/starter), LLaMA-3 (pro) | 0.2 | buy/hold/sell + rationale |
| Report Generator | GPT-4o-mini | 0.1 | Full markdown decision report |

---

## Getting Started

### Prerequisites

- Docker & Docker Compose
- API keys for: OpenAI, Pinecone (optional), Stripe (optional)

### 1. Clone and setup env

```bash
git clone <repo>
cd finsight-saas

# Backend
cp backend/.env.example backend/.env
# Edit backend/.env with your API keys

# Frontend
cp frontend/.env.local.example frontend/.env.local
# Edit frontend/.env.local
```

### 2. Start all services

```bash
cd infra
docker-compose up -d

# Pull LLaMA-3 model for pro plan
docker exec finsight-ollama ollama pull llama3:8b
```

### 3. Open in browser

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000/docs |
| Celery Flower | http://localhost:5555 |

---

## Development (without Docker)

### Backend

```bash
cd finsight-saas

# Start PostgreSQL + Redis (via Docker)
docker-compose -f infra/docker-compose.yml up postgres redis -d

# Install dependencies
pip install -r backend/requirements.txt

# Run FastAPI
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Run Celery worker (separate terminal)
celery -A backend.core.queue.celery_app worker --loglevel=info
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## API Reference

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/register` | — | Register new user |
| POST | `/auth/token` | — | Login, get JWT |
| POST | `/analyze` | ✓ | Submit analysis job |
| GET | `/jobs/{id}/status` | ✓ | Poll job status |
| GET | `/reports` | ✓ | Paginated report history |
| GET | `/reports/{id}` | ✓ | Get single report |
| POST | `/upload-portfolio` | ✓ | Upload PDF for RAG |
| GET | `/usage` | ✓ | Current day usage |
| POST | `/billing/create-checkout-session` | ✓ | Stripe checkout |
| POST | `/webhooks/stripe` | — | Stripe webhooks |

---

## Multi-tenancy & Security

- **JWT claims:** `sub` (tenant_id), `email`, `plan`
- **Quota:** Redis key `usage:{tenant_id}:{date}` — enforced on every protected route
- **Vector isolation:** Pinecone `namespace=tenant_id` — vectors never cross tenant boundaries
- **DB isolation:** `tenant_id` FK on every table + PostgreSQL Row Level Security
- **Plan limits:** Free=5/day, Starter=50/day, Pro=999,999/day

---

## Plan Comparison

| Feature | Free | Starter | Pro |
|---------|------|---------|-----|
| Queries/day | 5 | 50 | Unlimited |
| Forecast model | GPT-4o-mini | GPT-4o-mini | LLaMA-3 8B |
| PDF upload | ✓ | ✓ | ✓ |
| SEC EDGAR | — | ✓ | ✓ |
| Priority queue | — | ✓ | ✓ |
| Price | Free | ₹499/mo | ₹1,999/mo |

---

## Running Tests

```bash
cd finsight-saas
pytest backend/tests/ -v --asyncio-mode=auto
```

Test coverage:
- Quota logic (under/at/over limit, increment, pro unlimited)
- All 6 API endpoints (analyze, jobs, reports, upload, usage, billing)
- LangGraph state transitions (risk parser, sentiment parser, forecast parser)

---

## CI/CD

GitHub Actions workflow (`.github/workflows/ci-cd.yml`):

1. **test** job: Python pytest + Next.js build + TypeScript check
2. **build-and-deploy** job (main only): Docker build → Docker Hub → Railway webhook

### Required GitHub Secrets

```
DOCKER_USERNAME, DOCKER_PASSWORD
RAILWAY_BACKEND_WEBHOOK, RAILWAY_FRONTEND_WEBHOOK
NEXT_PUBLIC_API_URL
```

---

## Environment Variables

See `backend/.env.example` and `frontend/.env.local.example` for full reference.

---

## Monitoring

- **LangSmith**: Set `LANGCHAIN_API_KEY` to trace every LLM call through the agent pipeline
- **Sentry**: Set `SENTRY_DSN` for error tracking in FastAPI
- **Flower**: Celery task monitoring at http://localhost:5555
