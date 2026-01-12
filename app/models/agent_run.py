from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Column, JSON


class AgentRun(SQLModel, table=True):
    __tablename__ = "agent_runs"

    run_id: str = Field(primary_key=True)
    agent_name: str = Field(index=True)
    agent_version: str
    model: str
    environment: str = Field(index=True)
    status: str = Field(index=True)
    started_at: datetime = Field(index=True)
    ended_at: datetime
    error_type: Optional[str] = Field(default=None, index=True)
    error_message: Optional[str] = None
    trace_id: Optional[str] = Field(default=None, index=True)
    correlation_ids: list = Field(default=[], sa_column=Column(JSON))
    cost: dict = Field(default={}, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class AgentStep(SQLModel, table=True):
    __tablename__ = "agent_steps"

    step_id: str = Field(primary_key=True)
    run_id: str = Field(foreign_key="agent_runs.run_id", index=True)
    name: str
    status: str = Field(index=True)
    started_at: datetime = Field(index=True)
    ended_at: datetime
    latency_ms: int
    retries: int = 0
    input_summary: str
    output_summary: str


class ToolCall(SQLModel, table=True):
    __tablename__ = "tool_calls"

    call_id: str = Field(primary_key=True)
    run_id: str = Field(foreign_key="agent_runs.run_id", index=True)
    step_id: str = Field(foreign_key="agent_steps.step_id", index=True)
    tool_name: str = Field(index=True)
    status: str = Field(index=True)
    args_json: dict = Field(default={}, sa_column=Column(JSON))
    args_hash: str
    result_summary: str
    error_class: Optional[str] = Field(default=None, index=True)
    error_message: Optional[str] = None
    status_code: Optional[int] = None
    latency_ms: int
    retries: int = 0


class GuardrailEvent(SQLModel, table=True):
    __tablename__ = "guardrail_events"

    event_id: str = Field(primary_key=True)
    run_id: str = Field(foreign_key="agent_runs.run_id", index=True)
    step_id: Optional[str] = Field(default=None, foreign_key="agent_steps.step_id")
    call_id: Optional[str] = Field(default=None, foreign_key="tool_calls.call_id")
    type: str = Field(index=True)
    message: str
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
