import pytest
from sqlmodel import Session
from datetime import datetime
from app.core.db import engine
from app.use_cases.rca_orchestrator import RCAOrchestrator
from app.repositories.agent_run_repo import AgentRunRepository
from app.repositories.rca_repo import RCARepository
from app.schemas.agent_run import (
    AgentRunPayload,
    AgentStep,
    ToolCall,
    GuardrailEvent,
    CostSummary,
)


def test_rca_report_sufficient_evidence():
    """Test RCA report generation with sufficient evidence."""
    with Session(engine) as session:
        # Create agent run with sufficient evidence
        payload = AgentRunPayload(
            run_id="test-sufficient-001",
            agent_name="test-agent",
            agent_version="1.0.0",
            model="gpt-4",
            environment="dev",
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
            status="failure",
            error_type="ToolError",
            error_message="API schema mismatch",
            steps=[
                AgentStep(
                    step_id="step-1",
                    name="API Call",
                    status="failure",
                    started_at=datetime.utcnow(),
                    ended_at=datetime.utcnow(),
                    input_summary="Call external API",
                    output_summary="Failed with validation error",
                    retries=1,
                    latency_ms=500,
                )
            ],
            tool_calls=[
                ToolCall(
                    call_id="call-1",
                    step_id="step-1",
                    tool_name="external_api",
                    status="failure",
                    args_json={"param": "value"},
                    args_hash="hash123",
                    error_class="ValidationError",
                    error_message="Missing required field: user_id",
                    latency_ms=450,
                )
            ],
            guardrail_events=[
                GuardrailEvent(
                    event_id="guard-1",
                    type="schema_validation",
                    message="Schema validation triggered",
                )
            ],
            cost=CostSummary(tokens_prompt=100, tokens_completion=50, total_cost_usd=0.01),
        )

        # Ingest
        agent_run_repo = AgentRunRepository(session)
        run_id = agent_run_repo.upsert_agent_run(payload)

        # Create RCA run
        rca_repo = RCARepository(session)
        rca_run = rca_repo.create_rca_run("rca-sufficient-001", run_id)

        # Run RCA analysis
        orchestrator = RCAOrchestrator(session)
        orchestrator.run_rca_analysis(rca_run.rca_run_id)

        # Check report
        report_model = rca_repo.get_rca_report(rca_run.rca_run_id)
        assert report_model is not None
        assert report_model.insufficient_evidence is False
        assert report_model.category == "tool_schema_mismatch"

        # Check report contents
        report_json = report_model.report_json
        assert len(report_json["evidence_index"]) > 0
        assert len(report_json["hypotheses"]) > 0
        assert len(report_json["action_items"]) > 0


def test_rca_report_insufficient_evidence():
    """Test RCA report generation with insufficient evidence."""
    with Session(engine) as session:
        # Create agent run with insufficient evidence
        payload = AgentRunPayload(
            run_id="test-insufficient-001",
            agent_name="test-agent",
            agent_version="1.0.0",
            model="gpt-4",
            environment="dev",
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
            status="failure",
            error_message="Internal Server Error",
            steps=[
                AgentStep(
                    step_id="step-1",
                    name="Process",
                    status="success",
                    started_at=datetime.utcnow(),
                    ended_at=datetime.utcnow(),
                    input_summary="Processing request",
                    output_summary="Completed processing",
                    retries=0,
                    latency_ms=100,
                )
            ],
            tool_calls=[],  # No tool calls
            guardrail_events=[],  # No guardrails
            cost=CostSummary(tokens_prompt=50, tokens_completion=20),
        )

        # Ingest
        agent_run_repo = AgentRunRepository(session)
        run_id = agent_run_repo.upsert_agent_run(payload)

        # Create RCA run
        rca_repo = RCARepository(session)
        rca_run = rca_repo.create_rca_run("rca-insufficient-001", run_id)

        # Run RCA analysis
        orchestrator = RCAOrchestrator(session)
        orchestrator.run_rca_analysis(rca_run.rca_run_id)

        # Check report
        report_model = rca_repo.get_rca_report(rca_run.rca_run_id)
        assert report_model is not None
        assert report_model.insufficient_evidence is True

        # Check report contents
        report_json = report_model.report_json
        assert len(report_json["hypotheses"]) == 0  # No hypotheses in insufficient mode
        assert len(report_json["action_items"]) > 0  # Still have data collection actions
