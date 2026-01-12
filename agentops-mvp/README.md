# AgentOps Smart SRE

Production-lean MVP for AgentOps: ingest structured Agent Run telemetry, replay it, run async RCA (Root Cause Analysis), stream progress via SSE, and expose basic metrics.

## Features

- **Structured Telemetry Ingestion**: Ingest agent runs with steps, tool calls, and guardrail events
- **Async RCA Analysis**: Evidence-first, anti-hallucination root cause analysis
- **Real-time Progress Streaming**: SSE streaming of RCA job progress
- **Metrics Dashboard**: Basic AgentOps metrics (success rate, failing tools, latency, cost)
- **Clean Architecture**: Business logic independent from FastAPI/RQ
- **Docker-Ready**: Full containerized deployment with docker-compose

## Architecture

```
├── app/
│   ├── main.py                 # FastAPI application
│   ├── core/                   # Infrastructure
│   │   ├── settings.py
│   │   ├── logging.py
│   │   ├── db.py
│   │   └── redis_clients.py
│   ├── schemas/                # Pydantic data contracts
│   │   ├── agent_run.py
│   │   └── rca.py
│   ├── models/                 # SQLModel database models
│   │   ├── agent_run.py
│   │   └── rca_run.py
│   ├── repositories/           # Data access layer
│   │   ├── agent_run_repo.py
│   │   └── rca_repo.py
│   ├── services/               # Business services
│   │   ├── progress.py
│   │   ├── strategy_library.py
│   │   └── llm_engine.py
│   ├── use_cases/              # Core business logic
│   │   └── rca_orchestrator.py
│   ├── api/                    # FastAPI routers
│   │   ├── agent_runs.py
│   │   ├── rca_runs.py
│   │   ├── stream.py
│   │   └── metrics.py
│   └── workers/                # RQ workers
│       ├── tasks.py
│       └── worker.py
└── tests/                      # Tests
```

## Tech Stack

- **Language**: Python 3.11
- **Web Framework**: FastAPI
- **Data Contracts**: Pydantic v2
- **Database**: PostgreSQL
- **Queue**: RQ + Redis
- **Streaming**: SSE via Redis pub/sub
- **Containerization**: Docker + docker-compose

## Quick Start

### Prerequisites

- Docker and docker-compose installed
- 8GB RAM recommended

### 1. Clone and Setup

```bash
cd agentops-smart-sre
cp .env.example .env
```

### 2. Start Services

```bash
docker compose up --build
```

This starts:
- PostgreSQL on port 5432
- Redis on port 6379
- API on port 8000
- RQ Worker

### 3. Verify

```bash
curl http://localhost:8000/
```

Expected response:
```json
{
  "status": "ok",
  "service": "agentops-smart-sre"
}
```

## API Endpoints

### Ingest Agent Run

**POST** `/agent-runs`

Ingest agent run telemetry (upsert by run_id).

Headers:
- `X-Ingest-Secret` (optional): If `APP_INGEST_SECRET` is set in env

### Get Agent Run

**GET** `/agent-runs/{run_id}`

Get agent run metadata with counts.

### Get Timeline

**GET** `/agent-runs/{run_id}/timeline`

Get merged timeline of steps, tool calls, and guardrails for replay.

### Create RCA Run

**POST** `/agent-runs/{run_id}/rca-runs`

Create RCA run and enqueue async analysis job.

Returns:
```json
{
  "rca_run_id": "uuid"
}
```

### Get RCA Run

**GET** `/agent-runs/rca-runs/{rca_run_id}`

Get RCA run status and report (if done).

### Stream RCA Progress

**GET** `/rca-runs/{rca_run_id}/stream`

SSE stream of real-time RCA progress.

Example:
```bash
curl -N http://localhost:8000/rca-runs/{rca_run_id}/stream
```

### Get Metrics

**GET** `/metrics/overview?hours=24`

Get AgentOps metrics over last N hours.

## Example Workflows

### Workflow 1: Sufficient Evidence (Tool Schema Mismatch)

#### Step 1: Ingest Agent Run

```bash
curl -X POST http://localhost:8000/agent-runs \
  -H "Content-Type: application/json" \
  -d @- <<'EOF'
{
  "run_id": "run-001-sufficient",
  "agent_name": "customer-support-agent",
  "agent_version": "2.1.0",
  "model": "gpt-4-turbo",
  "environment": "prod",
  "started_at": "2024-01-15T10:30:00Z",
  "ended_at": "2024-01-15T10:30:45Z",
  "status": "failure",
  "error_type": "ToolCallError",
  "error_message": "Tool schema validation failed",
  "trace_id": "trace-abc-123",
  "correlation_ids": ["req-456", "session-789"],
  "steps": [
    {
      "step_id": "step-001",
      "name": "Plan customer inquiry",
      "status": "success",
      "started_at": "2024-01-15T10:30:00Z",
      "ended_at": "2024-01-15T10:30:05Z",
      "input_summary": "Customer asking about order status for order #12345",
      "output_summary": "Plan: 1) Look up order 2) Check shipping status 3) Format response",
      "retries": 0,
      "latency_ms": 5000
    },
    {
      "step_id": "step-002",
      "name": "Look up order details",
      "status": "failure",
      "started_at": "2024-01-15T10:30:05Z",
      "ended_at": "2024-01-15T10:30:15Z",
      "input_summary": "Query order database for order #12345",
      "output_summary": "Failed: tool call validation error",
      "retries": 2,
      "latency_ms": 10000
    },
    {
      "step_id": "step-003",
      "name": "Check shipping status",
      "status": "success",
      "started_at": "2024-01-15T10:30:15Z",
      "ended_at": "2024-01-15T10:30:25Z",
      "input_summary": "Query shipping API for tracking",
      "output_summary": "Shipping status: in transit",
      "retries": 0,
      "latency_ms": 10000
    },
    {
      "step_id": "step-004",
      "name": "Format response",
      "status": "failure",
      "started_at": "2024-01-15T10:30:25Z",
      "ended_at": "2024-01-15T10:30:45Z",
      "input_summary": "Format customer-facing response",
      "output_summary": "Could not complete due to missing order data",
      "retries": 0,
      "latency_ms": 20000
    }
  ],
  "tool_calls": [
    {
      "call_id": "call-001",
      "step_id": "step-002",
      "tool_name": "order_lookup_api",
      "status": "failure",
      "args_json": {
        "order_number": "12345",
        "include_items": true
      },
      "args_hash": "hash-order-lookup-001",
      "result_summary": "",
      "error_class": "ValidationError",
      "error_message": "Missing required field: 'customer_id'. API schema updated to v2.0 requiring customer_id",
      "status_code": 400,
      "retries": 2,
      "latency_ms": 350
    },
    {
      "call_id": "call-002",
      "step_id": "step-003",
      "tool_name": "shipping_status_api",
      "status": "success",
      "args_json": {
        "tracking_number": "TRACK-12345"
      },
      "args_hash": "hash-shipping-001",
      "result_summary": "Status: in transit, ETA: 2024-01-17",
      "error_class": null,
      "error_message": null,
      "status_code": 200,
      "retries": 0,
      "latency_ms": 9500
    },
    {
      "call_id": "call-003",
      "step_id": "step-002",
      "tool_name": "order_lookup_api",
      "status": "failure",
      "args_json": {
        "order_number": "12345",
        "include_items": true,
        "retry": true
      },
      "args_hash": "hash-order-lookup-002",
      "result_summary": "",
      "error_class": "ValidationError",
      "error_message": "Missing required field: 'customer_id'",
      "status_code": 400,
      "retries": 0,
      "latency_ms": 280
    }
  ],
  "guardrail_events": [
    {
      "event_id": "guard-001",
      "type": "schema_validation",
      "message": "Tool call failed schema validation: order_lookup_api missing customer_id parameter",
      "step_id": "step-002",
      "call_id": "call-001",
      "created_at": "2024-01-15T10:30:08Z"
    }
  ],
  "cost": {
    "tokens_prompt": 1250,
    "tokens_completion": 380,
    "total_cost_usd": 0.0245
  }
}
EOF
```

#### Step 2: Create RCA Run

```bash
curl -X POST http://localhost:8000/agent-runs/run-001-sufficient/rca-runs
```

Response:
```json
{
  "rca_run_id": "rca-abc-123"
}
```

#### Step 3: Stream Progress (in separate terminal)

```bash
curl -N http://localhost:8000/rca-runs/rca-abc-123/stream
```

Output:
```
data: {"status":"running","step":"Starting RCA","pct":5,"message":"Starting RCA","updated_at":"2024-01-15T10:31:00Z"}

data: {"status":"running","step":"Collecting evidence","pct":30,"message":"Collecting evidence","updated_at":"2024-01-15T10:31:02Z"}

data: {"status":"running","step":"Classifying failure","pct":55,"message":"Classifying failure","updated_at":"2024-01-15T10:31:04Z"}

data: {"status":"running","step":"Generating report","pct":85,"message":"Generating report","updated_at":"2024-01-15T10:31:06Z"}

data: {"status":"done","step":"RCA complete","pct":100,"message":"RCA complete","updated_at":"2024-01-15T10:31:08Z"}
```

#### Step 4: Get Report

```bash
curl http://localhost:8000/agent-runs/rca-runs/rca-abc-123
```

Response (abbreviated):
```json
{
  "rca_run_id": "rca-abc-123",
  "run_id": "run-001-sufficient",
  "status": "done",
  "report": {
    "category": "tool_schema_mismatch",
    "insufficient_evidence": false,
    "evidence_index": [
      {
        "evidence_id": "ev_tool_call-001",
        "kind": "tool_call",
        "ref_id": "call-001",
        "title": "Failed tool call: order_lookup_api",
        "snippet": "Missing required field: 'customer_id'. API schema updated to v2.0 requiring customer_id",
        "attributes": {
          "error_class": "ValidationError",
          "status_code": 400
        }
      }
    ],
    "hypotheses": [
      {
        "title": "Tool Schema Mismatch Root Cause",
        "description": "Tool call failed due to schema validation error...",
        "evidence_ids": ["ev_tool_call-001", "ev_guard_guard-001"],
        "confidence": "high",
        "verification_steps": [
          "Review tool call logs for detailed error traces",
          "Check external service status and API documentation"
        ]
      }
    ],
    "action_items": [
      {
        "type": "code_change",
        "title": "Update tool schema validation",
        "description": "Review and update tool argument schemas to match current API contract...",
        "priority": "high"
      }
    ]
  }
}
```

---

### Workflow 2: Insufficient Evidence

#### Step 1: Ingest Agent Run (Insufficient Evidence)

```bash
curl -X POST http://localhost:8000/agent-runs \
  -H "Content-Type: application/json" \
  -d @- <<'EOF'
{
  "run_id": "run-002-insufficient",
  "agent_name": "data-processor",
  "agent_version": "1.0.0",
  "model": "gpt-4",
  "environment": "staging",
  "started_at": "2024-01-15T11:00:00Z",
  "ended_at": "2024-01-15T11:00:30Z",
  "status": "failure",
  "error_type": null,
  "error_message": "Internal Server Error",
  "trace_id": null,
  "correlation_ids": [],
  "steps": [
    {
      "step_id": "step-101",
      "name": "Process data batch",
      "status": "success",
      "started_at": "2024-01-15T11:00:00Z",
      "ended_at": "2024-01-15T11:00:20Z",
      "input_summary": "Batch of 100 records",
      "output_summary": "Processed successfully",
      "retries": 0,
      "latency_ms": 20000
    },
    {
      "step_id": "step-102",
      "name": "Finalize",
      "status": "success",
      "started_at": "2024-01-15T11:00:20Z",
      "ended_at": "2024-01-15T11:00:30Z",
      "input_summary": "Finalize batch",
      "output_summary": "Completed",
      "retries": 0,
      "latency_ms": 10000
    }
  ],
  "tool_calls": [],
  "guardrail_events": [],
  "cost": {
    "tokens_prompt": 200,
    "tokens_completion": 50,
    "total_cost_usd": null
  }
}
EOF
```

#### Step 2: Create RCA Run

```bash
curl -X POST http://localhost:8000/agent-runs/run-002-insufficient/rca-runs
```

#### Step 3: Get Report

```bash
# Wait a few seconds for processing
sleep 5

curl http://localhost:8000/agent-runs/rca-runs/{rca_run_id}
```

Response (abbreviated):
```json
{
  "status": "done",
  "report": {
    "category": "unknown",
    "insufficient_evidence": true,
    "insufficient_reason": "Limited telemetry: no tool failures or specific error details captured",
    "evidence_index": [],
    "hypotheses": [],
    "action_items": [
      {
        "type": "monitoring",
        "title": "Enable detailed tracing",
        "description": "Add structured logging and tracing to capture more diagnostic information.",
        "priority": "high"
      },
      {
        "type": "code_change",
        "title": "Add structured error codes",
        "description": "Implement error code taxonomy to enable better classification in future RCAs.",
        "priority": "medium"
      }
    ]
  }
}
```

---

### Workflow 3: Get Metrics

```bash
curl "http://localhost:8000/metrics/overview?hours=24"
```

Response:
```json
{
  "total_runs": 42,
  "success_rate": 78.57,
  "top_failing_tools": [
    {"tool": "order_lookup_api", "count": 5},
    {"tool": "payment_api", "count": 3},
    {"tool": "inventory_check", "count": 2}
  ],
  "p95_step_latency_ms": 8500,
  "total_cost_usd": 1.234
}
```

## Running Tests

```bash
# Inside API container
docker compose exec api pytest -v tests/
```

Or locally:
```bash
pip install -r requirements.txt
pytest -v tests/
```

Expected output:
```
tests/test_ingest.py::test_ingest_agent_run PASSED
tests/test_ingest.py::test_get_agent_run PASSED
tests/test_rca_flow.py::test_create_rca_run PASSED
tests/test_rca_flow.py::test_rca_run_idempotency PASSED
tests/test_report.py::test_rca_report_sufficient_evidence PASSED
tests/test_report.py::test_rca_report_insufficient_evidence PASSED
```

## RCA Classification Categories

The system automatically classifies failures into:

- `tool_schema_mismatch`: Tool argument validation errors
- `rate_limited`: HTTP 429 or rate limit errors
- `tool_permission`: 401/403 permission errors
- `timeout`: Timeout errors
- `planner_loop`: Excessive retries (>=3)
- `retrieval_empty`: Empty search/retrieval results
- `prompt_regression`: Prompt behavior changes
- `unknown`: Unclassified failures

## Anti-Hallucination Policy

The system enforces evidence-first analysis:

1. **Insufficient Evidence Detection**:
   - No tool calls AND no error_type AND no guardrail events
   - Only generic error messages with no details

2. **Insufficient Evidence Mode**:
   - `insufficient_evidence: true`
   - Empty or low-confidence hypotheses
   - Action items focus on data collection

3. **Sufficient Evidence Mode**:
   - Hypotheses MUST cite evidence_ids
   - Verification steps included
   - Actionable mitigations provided

## Configuration

Environment variables (`.env`):

```env
# Database
DATABASE_URL=postgresql://user:pass@host:5432/db

# Redis
REDIS_URL=redis://host:6379/0

# API
APP_ENV=development
APP_INGEST_SECRET=           # Optional shared secret
LOG_LEVEL=INFO

# LLM (optional - disabled by default)
OPENAI_API_KEY=              # Leave empty for deterministic mode

# RQ
RQ_QUEUE_NAME=rca
```

## LLM Integration

The system operates in two modes:

1. **Disabled (default)**: Uses deterministic templates
2. **Enabled**: Set `OPENAI_API_KEY` for LLM-enhanced summaries

Even with LLM enabled, the anti-hallucination policy is enforced at the system level.

## Development

### Local Setup (without Docker)

```bash
# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL and Redis locally
# Update .env with local connection strings

# Run migrations (creates tables)
python -c "from app.core.db import init_db; init_db()"

# Start API
uvicorn app.main:app --reload

# Start worker (separate terminal)
python app/workers/worker.py
```

### Project Structure

The codebase follows clean architecture principles:

- **Core**: Infrastructure (settings, logging, db, redis)
- **Schemas**: Pydantic data contracts
- **Models**: SQLModel database models
- **Repositories**: Data access layer
- **Services**: Reusable business services
- **Use Cases**: Core business logic (orchestrators)
- **API**: FastAPI routers (thin layer)
- **Workers**: RQ background tasks

Business logic in `use_cases/` and `services/` is independent of FastAPI and RQ.

## Troubleshooting

### Database Not Ready

```bash
# Wait for postgres health check
docker compose logs postgres

# Manually create tables
docker compose exec api python -c "from app.core.db import init_db; init_db()"
```

### Worker Not Processing

```bash
# Check worker logs
docker compose logs worker

# Check RQ queue
docker compose exec api python -c "from rq import Queue; from app.core.redis_clients import get_sync_redis; q = Queue('rca', connection=get_sync_redis()); print(f'Jobs: {len(q)}')"
```

### Redis Connection Issues

```bash
# Test Redis
docker compose exec redis redis-cli ping
```

## License

MIT

## Contributing

This is an MVP. Contributions welcome for:
- Additional RCA classification patterns
- LLM integration enhancements
- Performance optimizations
- Additional test coverage
