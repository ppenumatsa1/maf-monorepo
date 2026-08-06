from __future__ import annotations

import logging

from app.core.config import Settings
from app.infrastructure.db.engine import create_db_engine
from app.infrastructure.foundry.responses_client import UnderwritingResponsesClient
from app.infrastructure.repositories.underwriting_repository import Repository
from app.modules.underwriting.copilot import (
    SAFE_EVENT_TYPES,
    SAFE_EXECUTOR_NAMES,
    SafeRunEvent,
    SafeRunExplanationRequest,
    SafeSelectedRunContext,
    build_safe_explanation,
    normalize_decision,
    normalize_status,
    normalize_timestamp,
)

logger = logging.getLogger(__name__)


class UnderwritingCopilotBridge:
    """Allowlisted bridge that projects a selected run without reading private payloads."""

    def __init__(
        self,
        settings: Settings,
        *,
        responses_client: UnderwritingResponsesClient | None = None,
        repository: Repository | None = None,
    ):
        self.settings = settings
        self.repository = repository or Repository(create_db_engine(settings))
        self._responses_client = responses_client or UnderwritingResponsesClient(settings)

    async def explain(self, workflow_run_id: str | None, intent: str) -> str:
        if workflow_run_id is None:
            return "Select an underwriting run to view its safe execution summary."
        context = self._safe_context(workflow_run_id)
        if context is None:
            return "The selected run is unavailable."
        expected_explanation = build_safe_explanation(context, intent)
        if self.settings.execution_mode == "local":
            return expected_explanation
        response = await self._responses_client.invoke(
            SafeRunExplanationRequest(
                workflow_run_id=workflow_run_id,
                intent=intent,
                context=context,
            )
        )
        # A hosted response is only accepted when it exactly matches the deterministic,
        # allowlisted projection. This prevents a malformed hosted response from leaking data.
        if (
            response.get("workflow_run_id") == workflow_run_id
            and response.get("explanation") == expected_explanation
        ):
            return expected_explanation
        logger.warning(
            "Hosted assistant response did not match the safe deterministic projection for run %s",
            workflow_run_id,
        )
        return expected_explanation

    def _safe_context(self, workflow_run_id: str) -> SafeSelectedRunContext | None:
        status = self.repository.get_safe_run_status(workflow_run_id)
        if status is None:
            return None
        events: list[SafeRunEvent] = []
        for event in self.repository.list_safe_event_summaries(workflow_run_id, limit=100):
            name = event.get("event_type")
            executor = event.get("executor_name")
            if name not in SAFE_EVENT_TYPES or executor not in SAFE_EXECUTOR_NAMES:
                continue
            events.append(
                SafeRunEvent(
                    name=name,
                    timestamp=normalize_timestamp(event.get("created_at")),
                    executor=executor,
                )
            )
        checkpoint_count, latest_checkpoint_at = self.repository.get_safe_checkpoint_summary(
            workflow_run_id
        )
        return SafeSelectedRunContext(
            workflow_run_id=workflow_run_id,
            status=normalize_status(status),
            events=tuple(events),
            checkpoint_count=checkpoint_count,
            latest_checkpoint_at=normalize_timestamp(latest_checkpoint_at),
            final_decision=normalize_decision(
                self.repository.get_safe_final_decision(workflow_run_id)
            ),
        )
