from datetime import datetime, timedelta
from typing import Optional
from sqlmodel import Session, select
from app.models.rca_run import RCArun, RCAReport


class RCARepository:
    def __init__(self, session: Session):
        self.session = session

    def create_rca_run(self, rca_run_id: str, run_id: str) -> RCArun:
        """Create a new RCA run."""
        rca_run = RCArun(
            rca_run_id=rca_run_id,
            run_id=run_id,
            status="queued",
            step="",
            pct=0,
            message="RCA job queued",
        )
        self.session.add(rca_run)
        self.session.commit()
        self.session.refresh(rca_run)
        return rca_run

    def get_rca_run(self, rca_run_id: str) -> Optional[RCArun]:
        """Get RCA run by ID."""
        return self.session.get(RCArun, rca_run_id)

    def update_rca_run_status(
        self,
        rca_run_id: str,
        status: str,
        step: str = "",
        pct: int = 0,
        message: str = "",
        error_message: Optional[str] = None,
    ) -> None:
        """Update RCA run status."""
        rca_run = self.get_rca_run(rca_run_id)
        if not rca_run:
            return

        rca_run.status = status
        rca_run.step = step
        rca_run.pct = pct
        rca_run.message = message

        if status == "running" and not rca_run.started_at:
            rca_run.started_at = datetime.utcnow()
        elif status in ["done", "error"]:
            rca_run.ended_at = datetime.utcnow()

        if error_message:
            rca_run.error_message = error_message

        self.session.add(rca_run)
        self.session.commit()

    def save_rca_report(
        self,
        report_id: str,
        rca_run_id: str,
        run_id: str,
        report_json: dict,
        insufficient_evidence: bool,
        category: str,
    ) -> RCAReport:
        """Save RCA report."""
        report = RCAReport(
            report_id=report_id,
            rca_run_id=rca_run_id,
            run_id=run_id,
            report_json=report_json,
            insufficient_evidence=insufficient_evidence,
            category=category,
        )
        self.session.add(report)
        self.session.commit()
        self.session.refresh(report)
        return report

    def get_rca_report(self, rca_run_id: str) -> Optional[RCAReport]:
        """Get RCA report by RCA run ID."""
        return self.session.exec(
            select(RCAReport).where(RCAReport.rca_run_id == rca_run_id)
        ).first()

    def find_recent_rca_run(self, run_id: str, minutes: int = 10) -> Optional[RCArun]:
        """Find recent RCA run for a given agent run."""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        return self.session.exec(
            select(RCArun)
            .where(
                RCArun.run_id == run_id,
                RCArun.status.in_(["queued", "running"]),
                RCArun.created_at >= cutoff,
            )
            .order_by(RCArun.created_at.desc())
        ).first()
