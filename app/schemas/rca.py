from datetime import datetime
from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field


class RCACategory(str, Enum):
    TOOL_SCHEMA_MISMATCH = "tool_schema_mismatch"
    RATE_LIMITED = "rate_limited"
    TOOL_PERMISSION = "tool_permission"
    TIMEOUT = "timeout"
    PLANNER_LOOP = "planner_loop"
    RETRIEVAL_EMPTY = "retrieval_empty"
    PROMPT_REGRESSION = "prompt_regression"
    UNKNOWN = "unknown"


class ActionItemType(str, Enum):
    CODE_CHANGE = "code_change"
    RUNBOOK = "runbook"
    CHANGE_CONFIG = "change_config"
    ROLLBACK = "rollback"
    MONITORING = "monitoring"
    TEST = "test"


class ActionItemPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidenceKind(str, Enum):
    STEP = "step"
    TOOL_CALL = "tool_call"
    GUARDRAIL = "guardrail"


class EvidenceRef(BaseModel):
    evidence_id: str
    kind: EvidenceKind
    ref_id: str  # step_id, call_id, or event_id
    title: str
    snippet: str
    attributes: dict = Field(default_factory=dict)


class Hypothesis(BaseModel):
    hypothesis_id: str = Field(default_factory=lambda: f"hyp_{datetime.utcnow().timestamp()}")
    title: str
    description: str
    evidence_ids: list[str]  # MUST reference evidence
    confidence: str  # high, medium, low
    verification_steps: list[str] = Field(default_factory=list)
    mitigation: Optional[str] = None


class ActionItem(BaseModel):
    action_id: str = Field(default_factory=lambda: f"act_{datetime.utcnow().timestamp()}")
    type: ActionItemType
    title: str
    description: str
    owner: Optional[str] = None
    priority: ActionItemPriority = ActionItemPriority.MEDIUM
    due_in_days: Optional[int] = None


class MetricsSnapshot(BaseModel):
    top_failing_tool: Optional[str] = None
    max_step_latency_ms: int = 0
    total_retries: int = 0
    total_cost_usd: Optional[float] = None


class JiraFields(BaseModel):
    jira_summary: str
    jira_description_md: str


class RCAReport(BaseModel):
    report_id: str
    rca_run_id: str
    run_id: str
    generated_at: datetime
    category: RCACategory
    insufficient_evidence: bool = False
    insufficient_reason: Optional[str] = None
    evidence_index: list[EvidenceRef] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    metrics_snapshot: MetricsSnapshot = Field(default_factory=MetricsSnapshot)
    jira_fields: Optional[JiraFields] = None


class RCARunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class RCARunResponse(BaseModel):
    rca_run_id: str
    run_id: str
    status: RCARunStatus
    step: str = ""
    pct: int = 0
    message: str = ""
    created_at: datetime
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    error_message: Optional[str] = None
    report: Optional[RCAReport] = None


class ProgressEvent(BaseModel):
    status: RCARunStatus
    step: str
    pct: int
    message: str
    updated_at: datetime
