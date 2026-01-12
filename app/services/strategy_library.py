from typing import Optional
from app.schemas.rca import RCACategory


class StrategyLibrary:
    """Deterministic pattern matching for RCA category classification."""

    @staticmethod
    def classify_category(
        error_type: Optional[str],
        error_message: Optional[str],
        tool_calls: list,
        steps: list,
        guardrails: list,
    ) -> RCACategory:
        """Classify the failure category based on telemetry patterns."""

        # Check tool calls for specific patterns
        for tool_call in tool_calls:
            if tool_call.status == "failure":
                # Rate limiting
                if tool_call.status_code == 429 or (
                    tool_call.error_message
                    and "rate limit" in tool_call.error_message.lower()
                ):
                    return RCACategory.RATE_LIMITED

                # Tool schema mismatch
                if tool_call.error_class and "schema" in tool_call.error_class.lower():
                    return RCACategory.TOOL_SCHEMA_MISMATCH
                if tool_call.error_message and any(
                    keyword in tool_call.error_message.lower()
                    for keyword in ["validation", "schema", "unexpected", "missing required"]
                ):
                    return RCACategory.TOOL_SCHEMA_MISMATCH

                # Permission issues
                if tool_call.status_code in [401, 403] or (
                    tool_call.error_message
                    and any(
                        keyword in tool_call.error_message.lower()
                        for keyword in ["permission", "unauthorized", "forbidden", "access denied"]
                    )
                ):
                    return RCACategory.TOOL_PERMISSION

                # Timeout
                if tool_call.error_class and "timeout" in tool_call.error_class.lower():
                    return RCACategory.TIMEOUT
                if tool_call.error_message and "timeout" in tool_call.error_message.lower():
                    return RCACategory.TIMEOUT

        # Check guardrails for schema validation
        for guardrail in guardrails:
            if guardrail.type == "schema_validation":
                return RCACategory.TOOL_SCHEMA_MISMATCH

        # Check steps for planner loop (excessive retries)
        max_retries = max((step.retries for step in steps), default=0)
        if max_retries >= 3:
            return RCACategory.PLANNER_LOOP

        # Check for retrieval empty (heuristic: low output with no errors)
        if not tool_calls and not error_type:
            # Could be retrieval_empty if there's a search/retrieval pattern
            for step in steps:
                if "retriev" in step.name.lower() or "search" in step.name.lower():
                    if len(step.output_summary) < 50:
                        return RCACategory.RETRIEVAL_EMPTY

        # Timeout at run level
        if error_type and "timeout" in error_type.lower():
            return RCACategory.TIMEOUT

        # Default: unknown
        return RCACategory.UNKNOWN
