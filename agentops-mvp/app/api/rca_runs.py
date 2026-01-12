from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from rq import Queue
from app.core.db import get_session
from app.core.redis_clients import get_sync_redis
from app.core.settings import settings
from app.core.logging import get_logger
from app.repositories.agent_run_repo import AgentRunRepository
from app.repositories.rca_repo import RCARepository
from app.schemas.rca import RCARunResponse, RCAReport

router = APIRouter(prefix="/agent-runs", tags=["RCA"])
logger = get_logger(__name__)


@router.post("/{run_id}/rca-runs", response_model=dict)
def create_rca_run(run_id: str, session: Session = Depends(get_session)):
    """Create RCA run and enqueue job."""
    # Check if agent run exists
    agent_run_repo = AgentRunRepository(session)
    if not agent_run_repo.get_agent_run(run_id):
        raise HTTPException(status_code=404, detail="Agent run not found")

    rca_repo = RCARepository(session)

    # Check for recent RCA run (idempotency)
    existing_rca = rca_repo.find_recent_rca_run(run_id, minutes=10)
    if existing_rca:
        logger.info(f"Found existing RCA run {existing_rca.rca_run_id} for run {run_id}")
        return {"rca_run_id": existing_rca.rca_run_id}

    # Create new RCA run
    rca_run_id = str(uuid4())
    rca_repo.create_rca_run(rca_run_id, run_id)

    # Enqueue RQ job
    redis_client = get_sync_redis()
    queue = Queue(settings.rq_queue_name, connection=redis_client)
    queue.enqueue("app.workers.tasks.run_rca_job", rca_run_id)

    logger.info(f"Created RCA run {rca_run_id} for agent run {run_id}")
    return {"rca_run_id": rca_run_id}


@router.get("/rca-runs/{rca_run_id}", response_model=RCARunResponse)
def get_rca_run(rca_run_id: str, session: Session = Depends(get_session)):
    """Get RCA run status and report if ready."""
    rca_repo = RCARepository(session)
    rca_run = rca_repo.get_rca_run(rca_run_id)

    if not rca_run:
        raise HTTPException(status_code=404, detail="RCA run not found")

    # Get report if done
    report = None
    if rca_run.status == "done":
        report_model = rca_repo.get_rca_report(rca_run_id)
        if report_model:
            report = RCAReport(**report_model.report_json)

    return RCARunResponse(
        rca_run_id=rca_run.rca_run_id,
        run_id=rca_run.run_id,
        status=rca_run.status,
        step=rca_run.step,
        pct=rca_run.pct,
        message=rca_run.message,
        created_at=rca_run.created_at,
        started_at=rca_run.started_at,
        ended_at=rca_run.ended_at,
        error_message=rca_run.error_message,
        report=report,
    )
