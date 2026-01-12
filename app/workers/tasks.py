from sqlmodel import Session
from app.core.db import engine
from app.core.logging import setup_logging, get_logger
from app.use_cases.rca_orchestrator import RCAOrchestrator

setup_logging()
logger = get_logger(__name__)


def run_rca_job(rca_run_id: str) -> None:
    """RQ task to run RCA analysis."""
    logger.info(f"Starting RCA job for {rca_run_id}")

    with Session(engine) as session:
        orchestrator = RCAOrchestrator(session)
        orchestrator.run_rca_analysis(rca_run_id)

    logger.info(f"Completed RCA job for {rca_run_id}")
