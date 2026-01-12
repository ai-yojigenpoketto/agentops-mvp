# AgentOps Debug UI - Quick Start Guide

## 🚀 Start Both Backend and Frontend

### Terminal 1: Start Backend (FastAPI + Worker)

```bash
cd /Users/leizhou/Documents/AI/projects/agentops-mvp

# Start all backend services
docker compose up -d

# Verify services are running
docker compose ps

# Check API is accessible
curl http://localhost:8000/
# Should return: {"status":"ok","service":"agentops-smart-sre"}
```

**Backend Services:**
- API: http://localhost:8000
- PostgreSQL: localhost:5432
- Redis: localhost:6379
- Worker: Background RQ worker

### Terminal 2: Start Frontend (Next.js UI)

```bash
cd /Users/leizhou/Documents/AI/projects/agentops-mvp

# Install dependencies (if not done yet)
npm install

# Start Next.js dev server
npm run dev
```

**Frontend:**
- UI: http://localhost:3000/debug

## 🎯 Run the Complete Debug Journey

1. Open browser to: **http://localhost:3000/debug**

2. Click the green button: **"▶ 一键跑完整流程"** (Run Journey)

3. Watch the automated flow:
   - ✅ Health check
   - ✅ Ingest agent run
   - ✅ Create RCA job
   - ✅ Poll until done
   - ✅ SSE connection (live progress)

4. **Check Results:**
   - Terminal log shows each step
   - Last HTTP Response shows final report
   - SSE Stream shows real-time progress
   - Report includes: category, evidence, hypotheses, action items

## 📊 Expected Output

### Terminal Log
```
[timestamp] → Health: GET /
[timestamp] ← Health: 200 OK
[timestamp] → Ingest: POST /agent-runs
[timestamp] ← Ingest: 200 OK
[timestamp] → Create RCA: POST /agent-runs/demo-run-001/rca-runs
[timestamp] ✓ rca_run_id = 52632d1d-dff9-4c13-a7cf-646821e07f12
[timestamp] ← Create RCA: 200 OK
[timestamp] ↻ Polling until done...
[timestamp] … status = queued
[timestamp] … status = running
[timestamp] … status = done
[timestamp] ✓ Poll finished: done
[timestamp]   → Category: tool_schema_mismatch
[timestamp]   → Insufficient Evidence: false
[timestamp]   → Evidence Count: 3
[timestamp] ↔ SSE connect: http://localhost:8000/rca-runs/.../stream
[timestamp] ✓ SSE connection opened
```

### SSE Stream
```
[timestamp] SSE connected
[timestamp] running | Starting RCA | 5% | Starting RCA
[timestamp] running | Collecting evidence | 30% | Collecting evidence
[timestamp] running | Classifying failure | 55% | Classifying failure
[timestamp] running | Generating report | 85% | Generating report
[timestamp] done | RCA complete | 100% | RCA complete
```

### Last HTTP Response (RCA Report)
```json
{
  "rca_run_id": "52632d1d-dff9-4c13-a7cf-646821e07f12",
  "run_id": "demo-run-001",
  "status": "done",
  "report": {
    "category": "tool_schema_mismatch",
    "insufficient_evidence": false,
    "evidence_index": [
      {
        "evidence_id": "ev_tool_...",
        "kind": "tool_call",
        "title": "Failed tool call: order_lookup_api",
        "snippet": "field required: order_id"
      },
      {
        "evidence_id": "ev_guard_...",
        "kind": "guardrail",
        "title": "Guardrail: schema_validation"
      }
    ],
    "hypotheses": [
      {
        "title": "Tool Schema Mismatch Root Cause",
        "confidence": "high",
        "evidence_ids": ["ev_tool_...", "ev_guard_..."]
      }
    ],
    "action_items": [
      {
        "type": "code_change",
        "title": "Update tool schema validation",
        "priority": "high"
      }
    ]
  }
}
```

## 🔧 Manual Step-by-Step Testing

If you prefer to test each step individually:

### 1. Health Check
```
Click: "Health" button
Expect: {"status":"ok","service":"agentops-smart-sre"}
```

### 2. Ingest
```
Click: "Ingest" button
Expect: {"run_id":"demo-run-001"}
```

### 3. Create RCA
```
Click: "Create RCA" button
Expect: {"rca_run_id":"<uuid>"}
Note: Copy the rca_run_id for next steps
```

### 4. Get RCA Status
```
Click: "Get RCA" button
Expect: Status changes from queued → running → done
```

### 5. Poll Until Done
```
Click: "Poll Until Done" button
Expect: Automated polling with status updates
Wait: ~5-10 seconds for completion
```

### 6. SSE Streaming
```
Click: "SSE Connect" button
Expect: Live progress events in SSE Stream panel
See: running | ... | 5% → 30% → 55% → 85% → 100%
Auto-disconnect: When done
```

## ❗ Troubleshooting

### Issue: CORS Error

**Symptom:**
```
✗ CORS ERROR: CORS blocked. Ensure FastAPI has CORSMiddleware...
```

**Solution:**
```bash
# Restart API to pick up CORS changes
docker compose restart api

# Verify CORS is configured
docker compose logs api | grep -i cors
```

### Issue: Connection Refused

**Symptom:**
```
✗ CORS ERROR: CORS blocked...
```

**Solution:**
```bash
# Check if API is running
docker compose ps

# If not running, start it
docker compose up -d api

# Check logs
docker compose logs api --tail 50
```

### Issue: Worker Not Processing

**Symptom:**
- RCA status stuck in "queued"
- No progress updates

**Solution:**
```bash
# Check worker is running
docker compose ps worker

# Check worker logs
docker compose logs worker --tail 50

# Restart worker
docker compose restart worker
```

### Issue: SSE Not Connecting

**Symptom:**
- SSE shows "(no SSE events yet)"
- Error in terminal

**Solution:**
1. Verify CORS is enabled (see above)
2. Check browser console for errors
3. Ensure rca_run_id is set
4. Try "Poll Until Done" first to ensure RCA is running

## 🎬 Interview Demo Script

**Perfect 2-minute demo:**

1. **Setup (15 seconds)**
   - "I built an AgentOps debug system with a FastAPI backend and Next.js UI"
   - Show both terminals running (docker compose, npm run dev)

2. **Run Journey (30 seconds)**
   - Click "Run Journey" button
   - "This executes the complete flow: health → ingest → RCA creation → polling → SSE"
   - Point to terminal log showing each step

3. **Show Results (45 seconds)**
   - "The terminal log proves every step worked"
   - "Last HTTP Response shows the structured RCA report"
   - "Category: tool_schema_mismatch - automatically classified"
   - "Evidence index with 3 pieces of evidence"
   - "Hypotheses with high confidence"
   - "Action items with priorities"

4. **Highlight Key Features (30 seconds)**
   - "SSE stream shows real-time progress"
   - "CORS is properly configured for browser clients"
   - "Error handling detects and explains common issues"
   - "All responses are machine-readable JSON"

## 📖 API Endpoints Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/agent-runs` | POST | Ingest agent run telemetry |
| `/agent-runs/{id}` | GET | Get agent run metadata |
| `/agent-runs/{id}/timeline` | GET | Get execution timeline |
| `/agent-runs/{id}/rca-runs` | POST | Create RCA analysis job |
| `/agent-runs/rca-runs/{id}` | GET | Get RCA status + report |
| `/rca-runs/{id}/stream` | GET | SSE progress stream |
| `/metrics/overview` | GET | AgentOps metrics |

## ✅ Success Criteria

You know it's working when:
- ✅ No CORS errors in browser console
- ✅ All HTTP responses return 200 status
- ✅ RCA status goes from queued → running → done
- ✅ SSE stream shows live progress events
- ✅ Final report includes category and action items
- ✅ Terminal log shows complete evidence trail

## 🔗 Next Steps

- Modify the payload in the UI to test different scenarios
- Test "insufficient evidence" case (remove tool_calls)
- View backend logs: `docker compose logs -f`
- Check metrics: `curl http://localhost:8000/metrics/overview?hours=24`
- Run tests: `docker compose exec api pytest -v tests/`
