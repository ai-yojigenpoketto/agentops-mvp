from fastapi import APIRouter, Depends, Query
from sqlmodel import Session
from app.core.db import get_session
from app.repositories.agent_run_repo import AgentRunRepository

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("/overview")
def get_metrics_overview(
    hours: int = Query(24, ge=1, le=168),
    session: Session = Depends(get_session),
):
    """Get basic AgentOps metrics."""
    repo = AgentRunRepository(session)
    metrics = repo.get_metrics_overview(hours)
    return metrics
