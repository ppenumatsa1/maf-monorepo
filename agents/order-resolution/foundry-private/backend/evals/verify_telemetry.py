from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential
from azure.monitor.query import LogsQueryClient, LogsQueryStatus

_SCENARIO_FIELDS = (
    "low_risk_thread_id",
    "high_risk_thread_id",
    "damaged_item_thread_id",
)
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]+$")


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _load_conversation_ids(evidence_path: Path) -> tuple[str, list[str]]:
    if not evidence_path.is_file():
        raise FileNotFoundError(f"Hosted E2E evidence is required: {evidence_path}")
    try:
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Hosted E2E evidence must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("Hosted E2E evidence must be a JSON object")
    started_at = payload.get("started_at", payload.get("generated_at"))
    if not isinstance(started_at, str) or not started_at:
        raise ValueError("Hosted E2E evidence must contain started_at")
    try:
        parsed_started_at = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Hosted E2E evidence started_at must be ISO 8601") from exc
    if parsed_started_at.tzinfo is None:
        raise ValueError("Hosted E2E evidence started_at must include a timezone")

    conversation_ids: list[str] = []
    for field in _SCENARIO_FIELDS:
        value = payload.get(field)
        if not isinstance(value, str) or not _SAFE_IDENTIFIER.fullmatch(value):
            raise ValueError(f"Hosted E2E evidence requires a valid {field}")
        conversation_ids.append(value)
    if len(set(conversation_ids)) != len(conversation_ids):
        raise ValueError("Hosted E2E evidence scenario conversation IDs must be unique")
    return started_at, conversation_ids


def _build_telemetry_query(
    started_at: str,
    conversation_ids: list[str],
    agent_id: str,
) -> str:
    return f"""
let e2eStartedAt = todatetime('{started_at}');
let conversationIds = dynamic({json.dumps(conversation_ids)});
let expectedAgentId = tostring(dynamic({json.dumps([agent_id])})[0]);
union isfuzzy=true traces, dependencies, requests, customEvents, exceptions
| where timestamp between (e2eStartedAt .. now())
| extend dimensions = tostring(customDimensions)
| extend genAiConversationId = tostring(parse_json(dimensions)["gen_ai.conversation.id"])
| extend genAiAgentId = tostring(parse_json(dimensions)["gen_ai.agent.id"])
| mv-expand conversationId = conversationIds
| where dimensions has tostring(conversationId)
| summarize
    matched_count = dcount(tostring(conversationId)),
    telemetry_rows = count(),
    trace_rows = countif(itemType == "trace"),
    dependency_rows = countif(itemType == "dependency"),
    request_rows = countif(itemType == "request"),
    exception_rows = countif(itemType == "exception"),
    evaluation_trace_conversation_count = dcountif(
        tostring(conversationId),
        dimensions has '"gen_ai.operation.name":"invoke_agent"'
            and dimensions has 'gen_ai.input.messages'
            and dimensions has 'gen_ai.output.messages'
            and genAiConversationId == tostring(conversationId)
            and genAiAgentId == expectedAgentId
    ),
    evaluation_trace_rows = countif(
        dimensions has '"gen_ai.operation.name":"invoke_agent"'
            and dimensions has 'gen_ai.input.messages'
            and dimensions has 'gen_ai.output.messages'
            and genAiConversationId == tostring(conversationId)
            and genAiAgentId == expectedAgentId
    )
"""


def _build_trace_ids_query(
    started_at: str,
    conversation_ids: list[str],
    agent_id: str,
) -> str:
    return f"""
let e2eStartedAt = todatetime('{started_at}');
let conversationIds = dynamic({json.dumps(conversation_ids)});
let expectedAgentId = tostring(dynamic({json.dumps([agent_id])})[0]);
union isfuzzy=true traces, dependencies, requests, customEvents, exceptions
| where timestamp between (e2eStartedAt .. now())
| extend dimensions = tostring(customDimensions)
| extend genAiConversationId = tostring(parse_json(dimensions)["gen_ai.conversation.id"])
| extend genAiAgentId = tostring(parse_json(dimensions)["gen_ai.agent.id"])
| mv-expand conversationId = conversationIds
| extend conversationId = tostring(conversationId)
| where dimensions has tostring(conversationId)
| where dimensions has '"gen_ai.operation.name":"invoke_agent"'
    and dimensions has 'gen_ai.input.messages'
    and dimensions has 'gen_ai.output.messages'
    and genAiConversationId == tostring(conversationId)
    and genAiAgentId == expectedAgentId
| summarize operation_Id = arg_max(timestamp, operation_Id) by conversationId
| summarize evaluation_trace_ids = make_set(operation_Id)
"""


def _query_row(
    client: LogsQueryClient,
    resource_id: str,
    query: str,
) -> dict[str, Any]:
    response = client.query_resource(resource_id, query=query, timespan=None)
    if response.status != LogsQueryStatus.SUCCESS:
        raise RuntimeError(
            f"Application Insights query returned {response.status}: "
            f"{getattr(response, 'partial_error', None)}"
        )
    if not response.tables or not response.tables[0].rows:
        return {}
    table = response.tables[0]
    columns = [
        column if isinstance(column, str) else column.name for column in table.columns
    ]
    return dict(zip(columns, table.rows[0], strict=True))


def _query_with_retries(
    client: LogsQueryClient,
    resource_id: str,
    query: str,
    *,
    max_attempts: int,
    retry_seconds: float,
) -> dict[str, Any]:
    for attempt in range(1, max_attempts + 1):
        try:
            return _query_row(client, resource_id, query)
        except (HttpResponseError, RuntimeError) as exc:
            print(
                f"Application Insights query attempt {attempt}/{max_attempts} failed: {exc}",
                flush=True,
            )
            if attempt == max_attempts:
                raise RuntimeError(
                    f"Application Insights query did not succeed after {max_attempts} attempts."
                ) from exc
            time.sleep(retry_seconds)
    raise AssertionError("Application Insights query retry loop must return or raise")


def _as_int(row: dict[str, Any], field: str) -> int:
    value = row.get(field, 0)
    return int(value) if value is not None else 0


def _trace_ids(row: dict[str, Any]) -> list[str]:
    value = row.get("evaluation_trace_ids", [])
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("Application Insights evaluation_trace_ids must be JSON") from exc
    if not isinstance(value, list):
        raise ValueError("Application Insights evaluation_trace_ids must be a list")
    return sorted(
        {
            trace_id
            for trace_id in value
            if isinstance(trace_id, str) and trace_id and trace_id == trace_id.strip()
        }
    )


def _write_result(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    evidence_path = root / os.getenv(
        "HOSTED_E2E_EVIDENCE_FILE", ".foundry/results/hosted-e2e-evidence.json"
    )
    result_path = root / os.getenv(
        "TELEMETRY_RESULT_FILE", ".foundry/results/telemetry-verification.json"
    )
    resource_id = _required_env("APPLICATION_INSIGHTS_RESOURCE_ID")
    agent_id = _required_env("FOUNDRY_EVALUATION_AGENT_ID")
    started_at, conversation_ids = _load_conversation_ids(evidence_path)
    max_attempts = int(os.getenv("TELEMETRY_MAX_ATTEMPTS", "24"))
    poll_seconds = float(os.getenv("TELEMETRY_POLL_SECONDS", "15"))
    query_max_attempts = int(os.getenv("APP_INSIGHTS_QUERY_MAX_ATTEMPTS", "3"))
    query_retry_seconds = float(os.getenv("APP_INSIGHTS_QUERY_RETRY_SECONDS", "5"))
    if min(max_attempts, query_max_attempts) <= 0:
        raise ValueError("Telemetry query attempt counts must be positive")

    telemetry_query = _build_telemetry_query(started_at, conversation_ids, agent_id)
    trace_ids_query = _build_trace_ids_query(started_at, conversation_ids, agent_id)
    credential = DefaultAzureCredential()
    client = LogsQueryClient(credential)
    try:
        for attempt in range(1, max_attempts + 1):
            row = _query_with_retries(
                client,
                resource_id,
                telemetry_query,
                max_attempts=query_max_attempts,
                retry_seconds=query_retry_seconds,
            )
            matched_count = _as_int(row, "matched_count")
            telemetry_rows = _as_int(row, "telemetry_rows")
            trace_rows = _as_int(row, "trace_rows")
            dependency_rows = _as_int(row, "dependency_rows")
            request_rows = _as_int(row, "request_rows")
            exception_rows = _as_int(row, "exception_rows")
            evaluation_trace_conversation_count = _as_int(
                row, "evaluation_trace_conversation_count"
            )
            evaluation_trace_rows = _as_int(row, "evaluation_trace_rows")
            evaluation_trace_ids: list[str] = []
            status = "waiting"

            if (
                telemetry_rows > 0
                and matched_count == len(conversation_ids)
                and evaluation_trace_conversation_count == len(conversation_ids)
                and evaluation_trace_rows > 0
                and exception_rows == 0
            ):
                trace_row = _query_with_retries(
                    client,
                    resource_id,
                    trace_ids_query,
                    max_attempts=query_max_attempts,
                    retry_seconds=query_retry_seconds,
                )
                evaluation_trace_ids = _trace_ids(trace_row)
                if len(evaluation_trace_ids) == len(conversation_ids):
                    status = "passed"

            result = {
                "status": status,
                "generated_at": datetime.now().astimezone().isoformat(),
                "e2e_started_at": started_at,
                "application_insights_resource_id": resource_id,
                "evaluation_agent_id": agent_id,
                "conversation_ids": conversation_ids,
                "matched_conversation_count": matched_count,
                "telemetry_rows": telemetry_rows,
                "trace_rows": trace_rows,
                "dependency_rows": dependency_rows,
                "request_rows": request_rows,
                "exception_rows": exception_rows,
                "evaluation_trace_conversation_count": evaluation_trace_conversation_count,
                "evaluation_trace_rows": evaluation_trace_rows,
                "evaluation_trace_ids": evaluation_trace_ids,
            }
            _write_result(result_path, result)
            if status == "passed":
                print(
                    "Application Insights telemetry check passed: "
                    f"{telemetry_rows} correlated rows and {evaluation_trace_rows} eligible "
                    f"Foundry evaluation spans for {matched_count} hosted E2E conversations."
                )
                return
            print(
                "Awaiting eligible evaluation telemetry "
                f"(attempt {attempt}/{max_attempts}; rows={telemetry_rows}, "
                f"conversations={matched_count}/{len(conversation_ids)}, "
                f"evaluation_conversations={evaluation_trace_conversation_count}/"
                f"{len(conversation_ids)}, evaluation_rows={evaluation_trace_rows}, "
                f"exceptions={exception_rows})."
            )
            time.sleep(poll_seconds)
    finally:
        credential.close()

    result["status"] = "failed"
    _write_result(result_path, result)
    raise RuntimeError(
        "Application Insights telemetry was not correlated to all current "
        "hosted E2E conversations within the bounded wait."
    )


if __name__ == "__main__":
    main()
