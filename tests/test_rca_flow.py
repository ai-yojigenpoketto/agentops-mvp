import pytest
from fastapi.testclient import TestClient
from datetime import datetime
from app.main import app

client = TestClient(app)


def test_create_rca_run():
    """Test creating an RCA run."""
    # First ingest an agent run
    payload = {
        "run_id": "test-run-rca-001",
        "agent_name": "test-agent",
        "agent_version": "1.0.0",
        "model": "gpt-4",
        "environment": "dev",
        "started_at": datetime.utcnow().isoformat(),
        "ended_at": datetime.utcnow().isoformat(),
        "status": "failure",
        "error_type": "RateLimitError",
        "error_message": "Rate limit exceeded",
        "steps": [
            {
                "step_id": "step-1",
                "name": "Execute",
                "status": "failure",
                "started_at": datetime.utcnow().isoformat(),
                "ended_at": datetime.utcnow().isoformat(),
                "input_summary": "Execute API call",
                "output_summary": "Failed with rate limit",
                "retries": 1,
                "latency_ms": 1000,
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
                "status_code": 429,
                "error_message": "Rate limit exceeded",
                "latency_ms": 900,
            }
        ],
        "guardrail_events": [],
        "cost": {"tokens_prompt": 100, "tokens_completion": 50},
    }

    response = client.post("/agent-runs", json=payload)
    assert response.status_code == 200

    # Create RCA run
    response = client.post("/agent-runs/test-run-rca-001/rca-runs")
    assert response.status_code == 200
    data = response.json()
    assert "rca_run_id" in data

    rca_run_id = data["rca_run_id"]

    # Get RCA run status
    response = client.get(f"/agent-runs/rca-runs/{rca_run_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["rca_run_id"] == rca_run_id
    assert data["run_id"] == "test-run-rca-001"
    assert data["status"] in ["queued", "running", "done"]


def test_rca_run_idempotency():
    """Test that duplicate RCA runs are not created."""
    # Create first RCA run
    test_create_rca_run()

    # Try to create another immediately
    response = client.post("/agent-runs/test-run-rca-001/rca-runs")
    assert response.status_code == 200
    data = response.json()
    # Should return existing RCA run ID
    assert "rca_run_id" in data
