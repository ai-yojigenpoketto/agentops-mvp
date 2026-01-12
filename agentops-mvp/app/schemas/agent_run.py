from datetime import datetime
from typing import Optional
from uuid import uuid4
from pydantic import BaseModel, Field, field_validator


class CostSummary(BaseModel):
    tokens_prompt: int = 0
    tokens_completion: int = 0
    total_cost_usd: Optional[float] = None


class AgentStep(BaseModel):
    step_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    status: str
    started_at: datetime
    ended_at: datetime
    input_summary: str = Field(max_length=2000)
    output_summary: str = Field(max_length=2000)
    retries: int = 0
    latency_ms: int = 0

    @field_validator("latency_ms", mode="before")
    @classmethod
    def compute_latency(cls, v: int, info) -> int:
        if v > 0:
            return v
        # Calculate from timestamps if not provided
        data = info.data
        if "started_at" in data and "ended_at" in data:
            delta = data["ended_at"] - data["started_at"]
            return int(delta.total_seconds() * 1000)
        return 0


class ToolCall(BaseModel):
    call_id: str = Field(default_factory=lambda: str(uuid4()))
    step_id: str
    tool_name: str
    status: str
    args_json: dict = Field(default_factory=dict)
    args_hash: str = ""
    result_summary: str = Field(max_length=2000, default="")
    error_class: Optional[str] = None
    error_message: Optional[str] = None
    status_code: Optional[int] = None
    retries: int = 0
    latency_ms: int = 0


class GuardrailEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    type: str  # pii_redaction, policy_block, schema_validation, other
    message: str
    step_id: Optional[str] = None
    call_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AgentRunPayload(BaseModel):
    run_id: Optional[str] = Field(default_factory=lambda: str(uuid4()))
    agent_name: str
    agent_version: str
    model: str
    environment: str  # prod, staging, dev
    started_at: datetime
    ended_at: datetime
    status: str  # success, failure
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    trace_id: Optional[str] = None
    correlation_ids: list[str] = Field(default_factory=list)
    steps: list[AgentStep] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    guardrail_events: list[GuardrailEvent] = Field(default_factory=list)
    cost: CostSummary = Field(default_factory=CostSummary)


class AgentRunResponse(BaseModel):
    run_id: str
    agent_name: str
    status: str
    started_at: datetime
    ended_at: datetime
    step_count: int
    tool_call_count: int
    guardrail_event_count: int


class TimelineEvent(BaseModel):
    event_id: str
    event_type: str  # step, tool_call, guardrail
    timestamp: datetime
    name: str
    status: str
    details: dict
