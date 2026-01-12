from typing import Optional
from app.core.settings import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class LLMEngine:
    """LLM integration for summarization and action item generation.

    Operates in two modes:
    1. Disabled (default): Uses deterministic templates
    2. Enabled (if OPENAI_API_KEY set): Calls LLM for enhanced summaries
    """

    def __init__(self):
        self.enabled = bool(settings.openai_api_key)
        if not self.enabled:
            logger.info("LLM engine running in DISABLED mode (deterministic templates)")
        else:
            logger.info("LLM engine running in ENABLED mode")

    def summarize_evidence(self, evidence_list: list) -> str:
        """Summarize evidence (deterministic template for MVP)."""
        if not self.enabled:
            return self._deterministic_summary(evidence_list)

        # If enabled, could call LLM here
        # For MVP, we'll use deterministic even if enabled
        return self._deterministic_summary(evidence_list)

    def _deterministic_summary(self, evidence_list: list) -> str:
        """Create a deterministic summary of evidence."""
        summary_parts = []
        for evidence in evidence_list:
            summary_parts.append(f"- {evidence.get('title', 'Evidence')}: {evidence.get('snippet', '')[:100]}")
        return "\n".join(summary_parts) if summary_parts else "No evidence available."

    def generate_hypothesis_description(
        self, category: str, evidence_snippets: list[str]
    ) -> str:
        """Generate hypothesis description (deterministic for MVP)."""
        if not self.enabled:
            return self._deterministic_hypothesis(category, evidence_snippets)

        # If enabled, could call LLM here
        return self._deterministic_hypothesis(category, evidence_snippets)

    def _deterministic_hypothesis(self, category: str, evidence_snippets: list[str]) -> str:
        """Create deterministic hypothesis based on category."""
        templates = {
            "tool_schema_mismatch": "Tool call failed due to schema validation error. The tool arguments did not match the expected schema, likely due to API changes or incorrect parameter formatting.",
            "rate_limited": "Tool call was rate limited (HTTP 429). The system exceeded the API rate limit, suggesting high request volume or insufficient rate limit configuration.",
            "tool_permission": "Tool call failed due to permission error. The agent lacks necessary credentials or permissions to execute the requested action.",
            "timeout": "Operation timed out before completion. The tool or step exceeded configured timeout limits, possibly due to slow external service or large data processing.",
            "planner_loop": "Agent entered a retry loop with excessive retries. The planner may be stuck in a cycle, repeatedly attempting the same failed operation.",
            "retrieval_empty": "Retrieval operation returned empty or insufficient results. The search/query did not find relevant data, possibly due to incorrect query formulation or missing data.",
            "prompt_regression": "Prompt behavior changed unexpectedly. Model responses deviated from expected format, possibly due to prompt changes or model version update.",
            "unknown": "Failure cause could not be determined from available telemetry. Additional instrumentation or logging may be needed.",
        }
        base_description = templates.get(category, templates["unknown"])

        if evidence_snippets:
            base_description += f" Evidence shows: {'; '.join(evidence_snippets[:2])}."

        return base_description

    def generate_action_items(self, category: str, insufficient: bool) -> list[dict]:
        """Generate action items (deterministic for MVP)."""
        if insufficient:
            return [
                {
                    "type": "monitoring",
                    "title": "Enable detailed tracing",
                    "description": "Add structured logging and tracing to capture more diagnostic information.",
                    "priority": "high",
                },
                {
                    "type": "code_change",
                    "title": "Add structured error codes",
                    "description": "Implement error code taxonomy to enable better classification in future RCAs.",
                    "priority": "medium",
                },
            ]

        # Category-specific actions
        action_templates = {
            "tool_schema_mismatch": [
                {
                    "type": "code_change",
                    "title": "Update tool schema validation",
                    "description": "Review and update tool argument schemas to match current API contract. Add unit tests for schema validation.",
                    "priority": "high",
                },
                {
                    "type": "test",
                    "title": "Add integration tests for tool calls",
                    "description": "Create integration tests that validate tool schemas against live API endpoints.",
                    "priority": "medium",
                },
            ],
            "rate_limited": [
                {
                    "type": "change_config",
                    "title": "Implement rate limiting backoff",
                    "description": "Add exponential backoff and retry logic for rate-limited requests.",
                    "priority": "high",
                },
                {
                    "type": "monitoring",
                    "title": "Add rate limit monitoring",
                    "description": "Track API usage and alert before hitting rate limits.",
                    "priority": "high",
                },
            ],
            "tool_permission": [
                {
                    "type": "change_config",
                    "title": "Verify API credentials and permissions",
                    "description": "Audit all API keys and service account permissions. Update with required scopes.",
                    "priority": "critical",
                },
            ],
            "timeout": [
                {
                    "type": "change_config",
                    "title": "Increase timeout thresholds",
                    "description": "Review and adjust timeout configuration based on P95 latency metrics.",
                    "priority": "high",
                },
                {
                    "type": "code_change",
                    "title": "Optimize slow operations",
                    "description": "Profile and optimize operations that frequently approach timeout limits.",
                    "priority": "medium",
                },
            ],
        }

        return action_templates.get(category, [
            {
                "type": "runbook",
                "title": "Investigate root cause",
                "description": f"Manual investigation required for {category} failure category.",
                "priority": "high",
            }
        ])
