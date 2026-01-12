from datetime import datetime
from uuid import uuid4
from typing import Optional
from sqlmodel import Session
from app.core.logging import get_logger
from app.repositories.agent_run_repo import AgentRunRepository
from app.repositories.rca_repo import RCARepository
from app.services.progress import ProgressService
from app.services.strategy_library import StrategyLibrary
from app.services.llm_engine import LLMEngine
from app.schemas.rca import (
    RCAReport,
    RCACategory,
    RCARunStatus,
    EvidenceRef,
    EvidenceKind,
    Hypothesis,
    ActionItem,
    ActionItemType,
    ActionItemPriority,
    MetricsSnapshot,
    JiraFields,
)

logger = get_logger(__name__)


class RCAOrchestrator:
    """Orchestrates the RCA analysis process."""

    def __init__(
        self,
        session: Session,
        progress_service: Optional[ProgressService] = None,
        llm_engine: Optional[LLMEngine] = None,
    ):
        self.session = session
        self.agent_run_repo = AgentRunRepository(session)
        self.rca_repo = RCARepository(session)
        self.progress_service = progress_service or ProgressService()
        self.strategy_library = StrategyLibrary()
        self.llm_engine = llm_engine or LLMEngine()

    def run_rca_analysis(self, rca_run_id: str) -> None:
        """Execute complete RCA analysis workflow."""
        try:
            # Load RCA run
            rca_run = self.rca_repo.get_rca_run(rca_run_id)
            if not rca_run:
                logger.error(f"RCA run not found: {rca_run_id}")
                return

            # Check if already done (idempotency)
            if rca_run.status == "done":
                logger.info(f"RCA run {rca_run_id} already completed, skipping")
                return

            run_id = rca_run.run_id

            # Update status to running
            self._update_progress(rca_run_id, RCARunStatus.RUNNING, "Starting RCA", 5)
            self.rca_repo.update_rca_run_status(
                rca_run_id, "running", "starting", 5, "Starting RCA analysis"
            )

            # Step 1: Collect evidence
            self._update_progress(rca_run_id, RCARunStatus.RUNNING, "Collecting evidence", 30)
            evidence_index = self._collect_evidence(run_id)

            # Step 2: Classify category
            self._update_progress(rca_run_id, RCARunStatus.RUNNING, "Classifying failure", 55)
            agent_run_data = self.agent_run_repo.get_agent_run_full(run_id)
            if not agent_run_data:
                raise ValueError(f"Agent run not found: {run_id}")

            category = self.strategy_library.classify_category(
                error_type=agent_run_data["run"].error_type,
                error_message=agent_run_data["run"].error_message,
                tool_calls=agent_run_data["tool_calls"],
                steps=agent_run_data["steps"],
                guardrails=agent_run_data["guardrails"],
            )

            # Step 3: Check for insufficient evidence
            insufficient_evidence = self._check_insufficient_evidence(
                agent_run_data, evidence_index
            )

            # Step 4: Generate hypotheses and action items
            self._update_progress(rca_run_id, RCARunStatus.RUNNING, "Generating report", 85)
            hypotheses, action_items = self._generate_hypotheses_and_actions(
                category, evidence_index, insufficient_evidence
            )

            # Step 5: Compile metrics
            metrics = self._compile_metrics(agent_run_data)

            # Step 6: Generate Jira fields
            jira_fields = self._generate_jira_fields(
                run_id, category, hypotheses, action_items, insufficient_evidence
            )

            # Step 7: Create report
            report = RCAReport(
                report_id=str(uuid4()),
                rca_run_id=rca_run_id,
                run_id=run_id,
                generated_at=datetime.utcnow(),
                category=category,
                insufficient_evidence=insufficient_evidence,
                insufficient_reason=(
                    "Limited telemetry: no tool failures or specific error details captured"
                    if insufficient_evidence
                    else None
                ),
                evidence_index=evidence_index,
                hypotheses=hypotheses,
                action_items=action_items,
                metrics_snapshot=metrics,
                jira_fields=jira_fields,
            )

            # Step 8: Save report
            self.rca_repo.save_rca_report(
                report_id=report.report_id,
                rca_run_id=rca_run_id,
                run_id=run_id,
                report_json=report.model_dump(mode="json"),
                insufficient_evidence=insufficient_evidence,
                category=category.value,
            )

            # Step 9: Mark done
            self._update_progress(rca_run_id, RCARunStatus.DONE, "RCA complete", 100)
            self.rca_repo.update_rca_run_status(
                rca_run_id, "done", "completed", 100, "RCA analysis completed"
            )

            logger.info(f"RCA analysis completed for {rca_run_id}")

        except Exception as e:
            logger.exception(f"RCA analysis failed for {rca_run_id}: {str(e)}")
            self._update_progress(
                rca_run_id, RCARunStatus.ERROR, "RCA failed", 0, f"Error: {str(e)}"
            )
            self.rca_repo.update_rca_run_status(
                rca_run_id, "error", "failed", 0, "RCA failed", error_message=str(e)
            )

    def _update_progress(
        self, rca_run_id: str, status: RCARunStatus, step: str, pct: int, message: str = ""
    ) -> None:
        """Update progress via Redis."""
        self.progress_service.publish_progress(
            rca_run_id, status, step, pct, message or step
        )

    def _collect_evidence(self, run_id: str) -> list[EvidenceRef]:
        """Collect evidence from telemetry."""
        evidence = []
        agent_run_data = self.agent_run_repo.get_agent_run_full(run_id)

        if not agent_run_data:
            return evidence

        # Evidence from failed steps
        for step in agent_run_data["steps"]:
            if step.status == "failure":
                evidence.append(
                    EvidenceRef(
                        evidence_id=f"ev_step_{step.step_id}",
                        kind=EvidenceKind.STEP,
                        ref_id=step.step_id,
                        title=f"Failed step: {step.name}",
                        snippet=step.output_summary[:200],
                        attributes={
                            "latency_ms": step.latency_ms,
                            "retries": step.retries,
                        },
                    )
                )

        # Evidence from failed tool calls
        for tool_call in agent_run_data["tool_calls"]:
            if tool_call.status == "failure":
                evidence.append(
                    EvidenceRef(
                        evidence_id=f"ev_tool_{tool_call.call_id}",
                        kind=EvidenceKind.TOOL_CALL,
                        ref_id=tool_call.call_id,
                        title=f"Failed tool call: {tool_call.tool_name}",
                        snippet=(tool_call.error_message or "")[:200],
                        attributes={
                            "error_class": tool_call.error_class,
                            "status_code": tool_call.status_code,
                            "latency_ms": tool_call.latency_ms,
                        },
                    )
                )

        # Evidence from guardrails
        for guardrail in agent_run_data["guardrails"]:
            evidence.append(
                EvidenceRef(
                    evidence_id=f"ev_guard_{guardrail.event_id}",
                    kind=EvidenceKind.GUARDRAIL,
                    ref_id=guardrail.event_id,
                    title=f"Guardrail: {guardrail.type}",
                    snippet=guardrail.message[:200],
                    attributes={"type": guardrail.type},
                )
            )

        return evidence

    def _check_insufficient_evidence(
        self, agent_run_data: dict, evidence_index: list[EvidenceRef]
    ) -> bool:
        """Determine if evidence is insufficient for RCA."""
        # No tool calls AND no error_type AND no guardrail events
        if (
            not agent_run_data["tool_calls"]
            and not agent_run_data["run"].error_type
            and not agent_run_data["guardrails"]
        ):
            return True

        # Only generic error message with no tool failure details
        if (
            agent_run_data["run"].error_message
            and "internal server error" in agent_run_data["run"].error_message.lower()
            and not any(ev.kind == EvidenceKind.TOOL_CALL for ev in evidence_index)
        ):
            return True

        return False

    def _generate_hypotheses_and_actions(
        self,
        category: RCACategory,
        evidence_index: list[EvidenceRef],
        insufficient_evidence: bool,
    ) -> tuple[list[Hypothesis], list[ActionItem]]:
        """Generate hypotheses and action items."""
        hypotheses = []
        action_items = []

        if insufficient_evidence:
            # In insufficient mode: no root cause hypotheses, only data collection
            hypotheses = []
            # Generate data collection actions
            action_items_data = self.llm_engine.generate_action_items(
                category.value, insufficient=True
            )
        else:
            # Generate hypotheses that reference evidence
            evidence_ids = [ev.evidence_id for ev in evidence_index]
            evidence_snippets = [ev.snippet for ev in evidence_index[:3]]

            hypothesis_desc = self.llm_engine.generate_hypothesis_description(
                category.value, evidence_snippets
            )

            hypotheses.append(
                Hypothesis(
                    title=f"{category.value.replace('_', ' ').title()} Root Cause",
                    description=hypothesis_desc,
                    evidence_ids=evidence_ids[:5],  # Reference relevant evidence
                    confidence="high" if len(evidence_ids) >= 2 else "medium",
                    verification_steps=[
                        "Review tool call logs for detailed error traces",
                        "Check external service status and API documentation",
                        "Reproduce failure in isolated test environment",
                    ],
                    mitigation="Apply recommended action items below",
                )
            )

            # Generate category-specific actions
            action_items_data = self.llm_engine.generate_action_items(
                category.value, insufficient=False
            )

        # Convert action items to Pydantic models
        for item in action_items_data:
            action_items.append(
                ActionItem(
                    type=ActionItemType(item["type"]),
                    title=item["title"],
                    description=item["description"],
                    priority=ActionItemPriority(item["priority"]),
                    owner=item.get("owner"),
                    due_in_days=item.get("due_in_days"),
                )
            )

        return hypotheses, action_items

    def _compile_metrics(self, agent_run_data: dict) -> MetricsSnapshot:
        """Compile metrics snapshot."""
        # Find top failing tool
        tool_failures = {}
        for tool_call in agent_run_data["tool_calls"]:
            if tool_call.status == "failure":
                tool_failures[tool_call.tool_name] = tool_failures.get(tool_call.tool_name, 0) + 1

        top_failing_tool = max(tool_failures.items(), key=lambda x: x[1])[0] if tool_failures else None

        # Max step latency
        max_latency = max((step.latency_ms for step in agent_run_data["steps"]), default=0)

        # Total retries
        total_retries = sum(step.retries for step in agent_run_data["steps"]) + sum(
            tc.retries for tc in agent_run_data["tool_calls"]
        )

        # Cost
        cost_data = agent_run_data["run"].cost
        total_cost = cost_data.get("total_cost_usd") if isinstance(cost_data, dict) else None

        return MetricsSnapshot(
            top_failing_tool=top_failing_tool,
            max_step_latency_ms=max_latency,
            total_retries=total_retries,
            total_cost_usd=total_cost,
        )

    def _generate_jira_fields(
        self,
        run_id: str,
        category: RCACategory,
        hypotheses: list[Hypothesis],
        action_items: list[ActionItem],
        insufficient_evidence: bool,
    ) -> JiraFields:
        """Generate Jira ticket fields."""
        summary = f"[AgentOps RCA] {category.value.replace('_', ' ').title()} - Run {run_id[:8]}"

        description_parts = [
            f"# RCA Report: {category.value}",
            f"**Run ID:** {run_id}",
            f"**Insufficient Evidence:** {insufficient_evidence}",
            "",
            "## Hypotheses",
        ]

        if hypotheses:
            for hyp in hypotheses:
                description_parts.append(f"### {hyp.title}")
                description_parts.append(f"- **Confidence:** {hyp.confidence}")
                description_parts.append(f"- **Description:** {hyp.description}")
                description_parts.append(f"- **Evidence Count:** {len(hyp.evidence_ids)}")
        else:
            description_parts.append("*Insufficient evidence to form hypotheses. Data collection required.*")

        description_parts.append("")
        description_parts.append("## Action Items")
        for action in action_items:
            description_parts.append(
                f"- [{action.priority.value.upper()}] **{action.title}** ({action.type.value})"
            )
            description_parts.append(f"  {action.description}")

        return JiraFields(
            jira_summary=summary,
            jira_description_md="\n".join(description_parts),
        )
