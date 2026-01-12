from datetime import datetime, timedelta
from typing import Optional
from sqlmodel import Session, select, func, desc
from app.models.agent_run import AgentRun, AgentStep, ToolCall, GuardrailEvent
from app.schemas.agent_run import AgentRunPayload, TimelineEvent


class AgentRunRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert_agent_run(self, payload: AgentRunPayload) -> str:
        """Upsert agent run and related data."""
        run_id = payload.run_id or ""

        # Upsert agent run
        existing_run = self.session.get(AgentRun, run_id)
        if existing_run:
            # Update existing
            for key, value in payload.model_dump(exclude={"steps", "tool_calls", "guardrail_events"}).items():
                setattr(existing_run, key, value)
            # Delete existing children
            self.session.exec(select(AgentStep).where(AgentStep.run_id == run_id)).all()
            for step in self.session.exec(select(AgentStep).where(AgentStep.run_id == run_id)):
                self.session.delete(step)
            for tool_call in self.session.exec(select(ToolCall).where(ToolCall.run_id == run_id)):
                self.session.delete(tool_call)
            for event in self.session.exec(select(GuardrailEvent).where(GuardrailEvent.run_id == run_id)):
                self.session.delete(event)
        else:
            # Create new
            run = AgentRun(
                **payload.model_dump(exclude={"steps", "tool_calls", "guardrail_events"})
            )
            self.session.add(run)

        # Insert steps
        for step_data in payload.steps:
            step = AgentStep(**step_data.model_dump(), run_id=run_id)
            self.session.add(step)

        # Insert tool calls
        for tool_call_data in payload.tool_calls:
            tool_call = ToolCall(**tool_call_data.model_dump(), run_id=run_id)
            self.session.add(tool_call)

        # Flush to ensure steps and tool_calls are committed before guardrails (for FK constraints)
        self.session.flush()

        # Insert guardrail events
        for event_data in payload.guardrail_events:
            event = GuardrailEvent(**event_data.model_dump(), run_id=run_id)
            self.session.add(event)

        self.session.commit()
        return run_id

    def get_agent_run(self, run_id: str) -> Optional[AgentRun]:
        """Get agent run by ID."""
        return self.session.get(AgentRun, run_id)

    def get_agent_run_full(self, run_id: str) -> Optional[dict]:
        """Get agent run with all related data."""
        run = self.get_agent_run(run_id)
        if not run:
            return None

        steps = self.session.exec(
            select(AgentStep).where(AgentStep.run_id == run_id).order_by(AgentStep.started_at)
        ).all()

        tool_calls = self.session.exec(
            select(ToolCall).where(ToolCall.run_id == run_id)
        ).all()

        guardrails = self.session.exec(
            select(GuardrailEvent).where(GuardrailEvent.run_id == run_id).order_by(GuardrailEvent.created_at)
        ).all()

        return {
            "run": run,
            "steps": steps,
            "tool_calls": tool_calls,
            "guardrails": guardrails,
        }

    def get_timeline(self, run_id: str) -> list[TimelineEvent]:
        """Get merged timeline of events."""
        data = self.get_agent_run_full(run_id)
        if not data:
            return []

        timeline = []

        # Add steps
        for step in data["steps"]:
            timeline.append(
                TimelineEvent(
                    event_id=step.step_id,
                    event_type="step",
                    timestamp=step.started_at,
                    name=step.name,
                    status=step.status,
                    details={
                        "input_summary": step.input_summary,
                        "output_summary": step.output_summary,
                        "latency_ms": step.latency_ms,
                        "retries": step.retries,
                    },
                )
            )

        # Add tool calls
        for tool_call in data["tool_calls"]:
            # Estimate timestamp from step
            step = next((s for s in data["steps"] if s.step_id == tool_call.step_id), None)
            timestamp = step.started_at if step else datetime.utcnow()
            timeline.append(
                TimelineEvent(
                    event_id=tool_call.call_id,
                    event_type="tool_call",
                    timestamp=timestamp,
                    name=tool_call.tool_name,
                    status=tool_call.status,
                    details={
                        "args_json": tool_call.args_json,
                        "result_summary": tool_call.result_summary,
                        "error_class": tool_call.error_class,
                        "error_message": tool_call.error_message,
                        "latency_ms": tool_call.latency_ms,
                    },
                )
            )

        # Add guardrails
        for event in data["guardrails"]:
            timeline.append(
                TimelineEvent(
                    event_id=event.event_id,
                    event_type="guardrail",
                    timestamp=event.created_at,
                    name=event.type,
                    status="triggered",
                    details={"message": event.message},
                )
            )

        # Sort by timestamp
        timeline.sort(key=lambda x: x.timestamp)
        return timeline

    def get_metrics_overview(self, hours: int = 24) -> dict:
        """Get basic AgentOps metrics."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        # Total runs
        total_runs = self.session.exec(
            select(func.count(AgentRun.run_id)).where(AgentRun.created_at >= cutoff)
        ).one()

        # Success rate
        successful_runs = self.session.exec(
            select(func.count(AgentRun.run_id)).where(
                AgentRun.created_at >= cutoff, AgentRun.status == "success"
            )
        ).one()
        success_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0.0

        # Top failing tools
        top_failing_tools = self.session.exec(
            select(ToolCall.tool_name, func.count(ToolCall.call_id).label("count"))
            .join(AgentRun, ToolCall.run_id == AgentRun.run_id)
            .where(AgentRun.created_at >= cutoff, ToolCall.status == "failure")
            .group_by(ToolCall.tool_name)
            .order_by(desc("count"))
            .limit(5)
        ).all()

        # P95 step latency (approximate)
        step_latencies = self.session.exec(
            select(AgentStep.latency_ms)
            .join(AgentRun, AgentStep.run_id == AgentRun.run_id)
            .where(AgentRun.created_at >= cutoff)
            .order_by(AgentStep.latency_ms)
        ).all()
        p95_latency = step_latencies[int(len(step_latencies) * 0.95)] if step_latencies else 0

        # Total cost
        runs_with_cost = self.session.exec(
            select(AgentRun.cost).where(AgentRun.created_at >= cutoff)
        ).all()
        total_cost = sum(
            cost.get("total_cost_usd", 0) for cost in runs_with_cost if cost.get("total_cost_usd")
        )

        return {
            "total_runs": total_runs,
            "success_rate": round(success_rate, 2),
            "top_failing_tools": [{"tool": tool, "count": count} for tool, count in top_failing_tools],
            "p95_step_latency_ms": p95_latency,
            "total_cost_usd": round(total_cost, 4) if total_cost else None,
        }
