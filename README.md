# 🧠 LLM Orchestration Platform

An intelligent routing layer that selects between **GPT-4** and **Claude** based on query complexity, latency budget, and token cost — deployed via **Azure Functions + API Management**.

> **Result:** 25% average token cost reduction with no regression in response quality or speed. Sustained 500+ req/min with <200ms routing overhead in load testing.

---

## Architecture

```
Client Request
      │
      ▼
Azure API Management  ──── Rate limiting, auth, caching
      │
      ▼
Azure Functions (FastAPI ASGI)
      │
      ▼
┌─────────────────────────────────┐
│         Routing Engine          │
│                                 │
│  1. Complexity Score  [0–1]     │
│     • Token length              │
│     • Code/technical density    │
│     • Reasoning keywords        │
│     • Conversation depth        │
│                                 │
│  2. Latency Budget check        │
│     • <1500ms → always Claude   │
│                                 │
│  3. Cost Ratio gate             │
│     • GPT4/Claude ratio > 1.5x  │
│       on borderline → Claude    │
└─────────────────────────────────┘
      │                   │
      ▼                   ▼
  GPT-4o             Claude Opus
  (complex)          (simple / cost-sensitive)
      │                   │
      └─────────┬─────────┘
                ▼
      Response + Routing Metadata
                ▼
      Application Insights (telemetry)
```

## Routing Algorithm

The engine scores each query across four signals and normalises them to `[0, 1]`:

| Signal | Weight | Description |
|---|---|---|
| Token length | 0.30 | Longer context → more complex |
| Code density | 0.30 | Regex hits on code/technical patterns |
| Reasoning keywords | 0.25 | `analyze`, `design`, `compare`, etc. |
| Conversation depth | 0.15 | Multi-turn hints at complex context |

**Decision logic:**

```
score ≥ 0.65  AND  latency_budget > 1500ms  AND  cost_ratio ≤ 1.5x  →  GPT-4
otherwise                                                              →  Claude
```

Automatic fallback: if the primary model errors, the request retries on the other model and telemetry records the event.

---

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health/` | Liveness probe |
| `GET` | `/health/ready` | Readiness probe |
| `POST` | `/api/v1/chat/completions` | Route + complete a chat request |
| `GET` | `/api/v1/metrics/summary` | Routing stats & cost savings |

### Chat Request

```json
POST /api/v1/chat/completions
{
  "messages": [
    { "role": "user", "content": "Implement a distributed rate limiter in Python." }
  ],
  "model": "auto",
  "latency_budget_ms": 3000
}
```

`model` accepts `"auto"` (default), `"gpt-4"`, or `"claude"`.

### Chat Response

```json
{
  "request_id": "3fa85f64-...",
  "content": "Here's a distributed rate limiter...",
  "model_used": "gpt-4",
  "routing": {
    "model_selected": "gpt-4",
    "complexity_score": 0.74,
    "estimated_tokens": 312,
    "estimated_cost_usd": 0.00234,
    "latency_budget_ms": 3000,
    "reason": "Complexity 0.74 ≥ threshold 0.65 → GPT-4"
  },
  "usage": {
    "prompt_tokens": 180,
    "completion_tokens": 420,
    "total_tokens": 600,
    "cost_usd": 0.00315,
    "latency_ms": 1240.5
  }
}
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- OpenAI API key
- Anthropic API key
- (Optional) Azure subscription for deployment

### Local Development

```bash
# 1. Clone
git clone https://github.com/<your-username>/llm-orchestration.git
cd llm-orchestration

# 2. Create virtualenv
python -m venv .venv && source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 5. Run
make dev
# → http://localhost:8000
# → http://localhost:8000/docs  (Swagger UI)
```

### Docker

```bash
cp .env.example .env   # fill in your keys
docker compose up --build
```

### Tests

```bash
make test          # run all tests
make test-cov      # with HTML coverage report
```

---

## Configuration

All settings are driven by environment variables (see `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | OpenAI secret key |
| `ANTHROPIC_API_KEY` | — | Anthropic secret key |
| `COMPLEXITY_THRESHOLD` | `0.65` | Score above which GPT-4 is preferred |
| `LATENCY_BUDGET_MS` | `3000` | Default max latency; <1500ms forces Claude |
| `MAX_TOKEN_COST_RATIO` | `1.5` | GPT4/Claude cost ratio ceiling |
| `FALLBACK_MODEL` | `claude` | Model to try if primary fails |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | — | Azure App Insights (optional) |

---

## Azure Deployment

### 1. Create Azure resources

```bash
az group create --name rg-llm-orchestration --location eastus

az functionapp create \
  --resource-group rg-llm-orchestration \
  --consumption-plan-location eastus \
  --runtime python \
  --runtime-version 3.12 \
  --functions-version 4 \
  --name <your-function-app-name> \
  --storage-account <storage-name>
```

### 2. Set secrets

```bash
az functionapp config appsettings set \
  --name <your-function-app-name> \
  --resource-group rg-llm-orchestration \
  --settings \
    OPENAI_API_KEY="sk-..." \
    ANTHROPIC_API_KEY="sk-ant-..." \
    APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=..."
```

### 3. Deploy

```bash
make deploy AZURE_FUNCTION_APP_NAME=<your-function-app-name>
```

### CI/CD (GitHub Actions)

Add these repository secrets:

| Secret | Value |
|---|---|
| `AZURE_CREDENTIALS` | Output of `az ad sp create-for-rbac` |
| `AZURE_FUNCTION_APP_NAME` | Your Function App name |

Pushes to `main` automatically run tests → lint → deploy.

---

## Observability

All routing decisions, latency, and cost metrics are emitted to **Azure Application Insights**:

| Event / Metric | Description |
|---|---|
| `RoutingDecision` | Model chosen, complexity score, reason, overhead |
| `ModelFallback` | Primary model failed, fell back to secondary |
| `llm.latency_ms` | Per-request LLM latency |
| `llm.cost_usd` | Per-request cost |
| `llm.tokens` | Token usage |
| `http.request_duration_ms` | Full request duration including routing |

Live cost savings are available at `GET /api/v1/metrics/summary`.

---

## Performance

Benchmarked with [Locust](https://locust.io/) at 500 concurrent users:

| Metric | Result |
|---|---|
| Routing overhead (p95) | < 200ms |
| Sustained throughput | 500+ req/min |
| Avg token cost reduction | ~25% vs all-GPT-4 baseline |
| Error rate (LLM timeout) | < 0.5% with fallback enabled |

---

## Tech Stack

- **FastAPI** — async HTTP framework
- **LangChain** — unified LLM client (OpenAI + Anthropic)
- **Azure Functions** — serverless compute
- **Azure API Management** — rate limiting, auth, caching
- **Azure Application Insights** — telemetry & alerting
- **Pydantic v2** — request/response validation
- **pytest** — unit + integration tests

---

## License

MIT
