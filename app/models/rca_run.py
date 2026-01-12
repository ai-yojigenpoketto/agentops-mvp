from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Column, JSON


class RCArun(SQLModel, table=True):
    __tablename__ = "rca_runs"

    rca_run_id: str = Field(primary_key=True)
    run_id: str = Field(foreign_key="agent_runs.run_id", index=True)
    status: str = Field(index=True)  # queued, running, done, error
    step: str = ""
    pct: int = 0
    message: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    error_message: Optional[str] = None


class RCAReport(SQLModel, table=True):
    __tablename__ = "rca_reports"

    report_id: str = Field(primary_key=True)
    rca_run_id: str = Field(foreign_key="rca_runs.rca_run_id", unique=True, index=True)
    run_id: str = Field(foreign_key="agent_runs.run_id", index=True)
    report_json: dict = Field(sa_column=Column(JSON))
    insufficient_evidence: bool = Field(default=False, index=True)
    category: str = Field(index=True)
    generated_at: datetime = Field(default_factory=datetime.utcnow, index=True)
