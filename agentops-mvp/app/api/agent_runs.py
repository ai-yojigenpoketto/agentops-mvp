from fastapi import APIRouter, Depends, HTTPException, Header
from sqlmodel import Session
from typing import Optional
from app.core.db import get_session
from app.core.settings import settings
from app.core.logging import get_logger
from app.repositories.agent_run_repo import AgentRunRepository
from app.schemas.agent_run import AgentRunPayload, AgentRunResponse, TimelineEvent

router = APIRouter(prefix="/agent-runs", tags=["Agent Runs"])
logger = get_logger(__name__)


def verify_ingest_secret(x_ingest_secret: Optional[str] = Header(None)) -> None:
    """Verify ingest secret if configured."""
    if settings.app_ingest_secret:
        if not x_ingest_secret or x_ingest_secret != settings.app_ingest_secret:
            raise HTTPException(status_code=403, detail="Invalid or missing ingest secret")


@router.post("", response_model=dict)
def ingest_agent_run(
    payload: AgentRunPayload,
    session: Session = Depends(get_session),
    _auth: None = Depends(verify_ingest_secret),
):
    """Ingest agent run telemetry."""
    repo = AgentRunRepository(session)
    run_id = repo.upsert_agent_run(payload)
    logger.info(f"Ingested agent run: {run_id}")
    return {"run_id": run_id}


@router.get("/{run_id}", response_model=AgentRunResponse)
def get_agent_run(run_id: str, session: Session = Depends(get_session)):
    """Get agent run metadata."""
    repo = AgentRunRepository(session)
    run_data = repo.get_agent_run_full(run_id)

    if not run_data:
        raise HTTPException(status_code=404, detail="Agent run not found")

    run = run_data["run"]
    return AgentRunResponse(
        run_id=run.run_id,
        agent_name=run.agent_name,
        status=run.status,
        started_at=run.started_at,
        ended_at=run.ended_at,
        step_count=len(run_data["steps"]),
        tool_call_count=len(run_data["tool_calls"]),
        guardrail_event_count=len(run_data["guardrails"]),
    )


@router.get("/{run_id}/timeline", response_model=list[TimelineEvent])
def get_agent_run_timeline(run_id: str, session: Session = Depends(get_session)):
    """Get merged timeline for replay."""
    repo = AgentRunRepository(session)
    timeline = repo.get_timeline(run_id)

    if not timeline:
        raise HTTPException(status_code=404, detail="Agent run not found")

    return timeline
