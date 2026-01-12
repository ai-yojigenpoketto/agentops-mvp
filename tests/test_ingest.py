import pytest
from fastapi.testclient import TestClient
from datetime import datetime
from app.main import app

client = TestClient(app)


def test_ingest_agent_run():
    """Test ingesting an agent run."""
    payload = {
        "run_id": "test-run-001",
        "agent_name": "test-agent",
        "agent_version": "1.0.0",
        "model": "gpt-4",
        "environment": "dev",
        "started_at": datetime.utcnow().isoformat(),
        "ended_at": datetime.utcnow().isoformat(),
        "status": "failure",
        "error_type": "ToolCallError",
        "error_message": "Schema validation failed",
        "steps": [
            {
                "step_id": "step-1",
                "name": "Planning",
                "status": "success",
                "started_at": datetime.utcnow().isoformat(),
                "ended_at": datetime.utcnow().isoformat(),
                "input_summary": "Plan task",
                "output_summary": "Created plan",
                "retries": 0,
                "latency_ms": 500,
            }
        ],
        "tool_calls": [
            {
                "call_id": "call-1",
                "step_id": "step-1",
                "tool_name": "api_call",
                "status": "failure",
                "args_json": {"endpoint": "/test"},
                "args_hash": "hash123",
                "error_class": "ValidationError",
                "error_message": "Missing required field",
                "latency_ms": 200,
            }
        ],
        "guardrail_events": [],
        "cost": {"tokens_prompt": 100, "tokens_completion": 50, "total_cost_usd": 0.01},
    }

    response = client.post("/agent-runs", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
    assert data["run_id"] == "test-run-001"


def test_get_agent_run():
    """Test retrieving an agent run."""
    # First ingest
    test_ingest_agent_run()

    # Then retrieve
    response = client.get("/agent-runs/test-run-001")
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == "test-run-001"
    assert data["agent_name"] == "test-agent"
    assert data["status"] == "failure"
