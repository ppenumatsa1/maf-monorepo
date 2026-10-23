from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

TERMINAL_EVALUATION_STATUSES = {"completed", "failed", "canceled"}
SUCCESSFUL_EVALUATION_STATUS = "completed"
FUTURE_CLOCK_SKEW = timedelta(minutes=5)


def _read_config(path: Path) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("backend/eval.yaml must be a mapping")
    return config


def _parse_utc_timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"Hosted smoke evidence is missing {field}")
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Hosted smoke evidence {field} must be ISO 8601") from exc
    if timestamp.tzinfo is None:
        raise ValueError(f"Hosted smoke evidence {field} must include a timezone")
    return timestamp.astimezone(UTC)


def _load_evidence(path: Path) -> tuple[datetime, list[str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Hosted smoke evidence must be a JSON object")
    generated_at = _parse_utc_timestamp(payload.get("generated_at"), "generated_at")
    conversation_ids = payload.get("conversation_ids")
    if not isinstance(conversation_ids, list):
        raise ValueError("Hosted smoke evidence is missing conversation_ids")
    valid_ids = [value for value in conversation_ids if isinstance(value, str) and value.strip()]
    if not valid_ids:
        raise ValueError("Hosted smoke evidence must contain at least one conversation ID")
    return generated_at, list(dict.fromkeys(valid_ids))


def _load_release_evidence(
    path: Path,
    *,
    max_age_seconds: float,
    now: datetime | None = None,
) -> tuple[datetime, list[str], str, datetime]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    generated_at, conversation_ids = _load_evidence(path)
    release_id = payload.get("release_id")
    if not isinstance(release_id, str) or not release_id:
        raise ValueError("Hosted smoke evidence is missing release_id")
    release_started_at = _parse_utc_timestamp(
        payload.get("release_started_at"),
        "release_started_at",
    )
    if generated_at < release_started_at:
        raise ValueError("Hosted smoke evidence predates the release window")
    current_time = (now or datetime.now(UTC)).astimezone(UTC)
    if generated_at > current_time + FUTURE_CLOCK_SKEW:
        raise ValueError("Hosted smoke evidence generated_at is in the future")
    if max_age_seconds <= 0 or current_time - generated_at > timedelta(seconds=max_age_seconds):
        raise ValueError("Hosted smoke evidence is stale")
    requested_release_id = os.getenv("RELEASE_ID", "").strip()
    if requested_release_id and requested_release_id != release_id:
        raise ValueError("Hosted smoke evidence belongs to a different release")
    requested_release_start = os.getenv("FOUNDRY_RELEASE_STARTED_AT", "").strip()
    if (
        requested_release_start
        and _parse_utc_timestamp(
            requested_release_start,
            "FOUNDRY_RELEASE_STARTED_AT",
        )
        != release_started_at
    ):
        raise ValueError("Hosted smoke evidence release start does not match")
    return generated_at, conversation_ids, release_id, release_started_at


def _criteria(evaluators: list[str], model: str) -> list[dict[str, Any]]:
    deployment_parameter_evaluators = {
        "task_completion",
        "task_adherence",
        "intent_resolution",
        "tool_call_accuracy",
        "tool_selection",
        "tool_input_accuracy",
        "tool_output_utilization",
        "tool_call_success",
    }
    return [
        {
            "type": "azure_ai_evaluator",
            "name": evaluator,
            "evaluator_name": f"builtin.{evaluator}",
            "initialization_parameters": {
                (
                    "deployment_name" if evaluator in deployment_parameter_evaluators else "model"
                ): model
            },
            "data_mapping": {"messages": "{{item.messages}}"},
        }
        for evaluator in evaluators
    ]


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _result_counts(value: object) -> dict[str, int]:
    if isinstance(value, dict):
        return {
            name: int(value.get(name, 0) or 0)
            for name in ("errored", "failed", "passed", "total", "skipped")
        }
    return {
        name: int(getattr(value, name, 0) or 0)
        for name in ("errored", "failed", "passed", "total", "skipped")
    }


def _criterion_result_counts(value: object) -> dict[str, int]:
    output_items = _to_jsonable(value)
    counts = {
        "errored": 0,
        "failed": 0,
        "passed": 0,
        "total": 0,
        "skipped": 0,
    }
    if not isinstance(output_items, list):
        return counts
    for output_item in output_items:
        if not isinstance(output_item, dict):
            continue
        results = output_item.get("results")
        if not isinstance(results, list):
            continue
        for criterion in results:
            if not isinstance(criterion, dict):
                continue
            counts["total"] += 1
            status = str(criterion.get("status") or "").lower()
            sample = criterion.get("sample")
            sample_error = sample.get("error") if isinstance(sample, dict) else None
            if status == "error" or sample_error not in (None, {}, ""):
                counts["errored"] += 1
            elif criterion.get("passed") is True:
                counts["passed"] += 1
            elif criterion.get("passed") is False:
                counts["failed"] += 1
            else:
                counts["skipped"] += 1
    return counts


def _to_jsonable(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    if hasattr(value, "model_dump"):
        return _to_jsonable(value.model_dump())
    if hasattr(value, "as_dict"):
        return _to_jsonable(value.as_dict())
    return str(value)


def _evidence_path(root: Path, configured: str) -> Path:
    return Path(os.getenv("FOUNDRY_SMOKE_EVIDENCE_FILE", root / configured))


def _is_transient_poll_error(error: Exception) -> bool:
    return isinstance(error, json.JSONDecodeError)


def _is_trace_readiness_error(error: object) -> bool:
    if not isinstance(error, dict):
        return False
    code = str(error.get("code") or "")
    message = str(error.get("message") or "")
    return code == "UserError" and "No trace data found for the provided conversation id" in message


def _should_retry_empty_evaluation(
    *,
    status: str,
    result_counts: object,
    error: object,
) -> bool:
    if error not in (None, {}, "") and not _is_trace_readiness_error(error):
        return False
    counts = _result_counts(result_counts)
    return status in {"completed", "failed"} and counts["total"] == 0


def run() -> None:
    root = Path(__file__).resolve().parents[1]
    config = _read_config(root / "eval.yaml")
    foundry = config.get("foundry")
    if not isinstance(foundry, dict):
        raise ValueError("backend/eval.yaml is missing the foundry configuration")
    trace_config = foundry.get("trace_evaluation")
    if not isinstance(trace_config, dict):
        raise ValueError("backend/eval.yaml is missing foundry.trace_evaluation")
    evidence_uri = trace_config.get("evidence_file")
    if not isinstance(evidence_uri, str) or not evidence_uri:
        raise ValueError("foundry.trace_evaluation.evidence_file is required")
    max_evidence_age = float(trace_config.get("max_evidence_age_seconds", 3600))
    generated_at, conversation_ids, release_id, release_started_at = _load_release_evidence(
        _evidence_path(root, evidence_uri),
        max_age_seconds=max_evidence_age,
    )

    evaluators = foundry.get("evaluators")
    if not isinstance(evaluators, list) or not all(
        isinstance(item, str) and item for item in evaluators
    ):
        raise ValueError("foundry.evaluators must be a non-empty list of evaluator names")
    project_endpoint = _required_env("FOUNDRY_PROJECTS_ENDPOINT")
    judge_model = _required_env("FOUNDRY_MODEL_DEPLOYMENT_NAME")
    timeout = float(os.getenv("FOUNDRY_EVAL_TIMEOUT", foundry.get("timeout", 900)))
    poll_interval = float(os.getenv("FOUNDRY_EVAL_POLL_INTERVAL", foundry.get("poll_interval", 5)))
    readiness_retry_seconds = float(
        os.getenv(
            "FOUNDRY_EVAL_READINESS_RETRY_SECONDS",
            trace_config.get("readiness_retry_seconds", 15),
        )
    )
    readiness_timeout_seconds = float(
        os.getenv(
            "FOUNDRY_EVAL_READINESS_TIMEOUT_SECONDS",
            trace_config.get("readiness_timeout_seconds", 240),
        )
    )
    if (
        timeout <= 0
        or poll_interval <= 0
        or readiness_retry_seconds <= 0
        or readiness_timeout_seconds < 0
    ):
        raise ValueError("Foundry evaluation timeout and retry values must be positive")
    evaluation_name = str(foundry.get("name", "underwriting-foundry-trace"))

    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(
            endpoint=project_endpoint,
            credential=credential,
        ) as project_client,
        project_client.get_openai_client() as openai_client,
    ):
        evaluation = openai_client.evals.create(
            name=evaluation_name,
            data_source_config={"type": "azure_ai_source", "scenario": "traces"},
            testing_criteria=_criteria(evaluators, judge_model),
        )
        evaluation_started = time.monotonic()
        readiness_started = evaluation_started
        readiness_attempts = 0
        while True:
            readiness_attempts += 1
            evaluation_run = openai_client.evals.runs.create(
                eval_id=evaluation.id,
                name=f"{evaluation_name}-run",
                metadata={
                    "release_id": release_id,
                    "trace_generated_at": generated_at.isoformat(),
                    "readiness_attempt": str(readiness_attempts),
                },
                data_source={
                    "type": "azure_ai_trace_data_source_preview",
                    "trace_source": {
                        "type": "conversation_id_source",
                        "conversation_ids": conversation_ids,
                    },
                },
                extra_body={"evaluation_level": "conversation"},
            )
            while str(evaluation_run.status) not in TERMINAL_EVALUATION_STATUSES:
                if time.monotonic() - evaluation_started >= timeout:
                    openai_client.evals.runs.cancel(
                        eval_id=evaluation.id,
                        run_id=evaluation_run.id,
                    )
                    raise TimeoutError(
                        f"Foundry trace evaluation timed out after {timeout} seconds"
                    )
                time.sleep(poll_interval)
                try:
                    evaluation_run = openai_client.evals.runs.retrieve(
                        eval_id=evaluation.id,
                        run_id=evaluation_run.id,
                    )
                except Exception as error:
                    if not _is_transient_poll_error(error):
                        raise
                    print(
                        "Foundry evaluation polling returned malformed JSON; "
                        "retrying within the run timeout."
                    )

            result_counts_value = getattr(evaluation_run, "result_counts", None)
            run_error = _to_jsonable(getattr(evaluation_run, "error", None))
            if not _should_retry_empty_evaluation(
                status=str(evaluation_run.status),
                result_counts=result_counts_value,
                error=run_error,
            ):
                break
            elapsed = time.monotonic() - readiness_started
            remaining = timeout - (time.monotonic() - evaluation_started)
            if (
                elapsed + readiness_retry_seconds > readiness_timeout_seconds
                or readiness_retry_seconds > remaining
            ):
                break
            print(
                "Foundry evaluation traces are not queryable yet; "
                f"retrying in {readiness_retry_seconds:g}s "
                f"(attempt {readiness_attempts})."
            )
            time.sleep(readiness_retry_seconds)

        output_items = list(
            openai_client.evals.runs.output_items.list(
                eval_id=evaluation.id,
                run_id=evaluation_run.id,
            )
        )

    result_counts = _result_counts(getattr(evaluation_run, "result_counts", None))
    criterion_result_counts = _criterion_result_counts(output_items)
    result = {
        "schema_version": 1,
        "evidence_type": "trace_evaluation",
        "release_id": release_id,
        "release_started_at": release_started_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "trace_evidence_generated_at": generated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": str(evaluation_run.status),
        "eval_id": evaluation.id,
        "run_id": evaluation_run.id,
        "conversation_ids": conversation_ids,
        "readiness_attempts": readiness_attempts,
        "result_counts": result_counts,
        "criterion_result_counts": criterion_result_counts,
        "error": _to_jsonable(getattr(evaluation_run, "error", None)),
        "output_items": _to_jsonable(output_items),
        "run_details": _to_jsonable(evaluation_run),
        "report_url": (
            f"{project_endpoint.rstrip('/')}/evaluation/evaluations/"
            f"{evaluation.id}/runs/{evaluation_run.id}"
        ),
    }
    configured_output = os.getenv("FOUNDRY_TRACE_EVAL_OUTPUT_FILE", "").strip()
    output = (
        Path(configured_output)
        if configured_output
        else root / ".foundry" / "results" / "foundry-trace-eval.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(json.dumps(result, indent=2, default=str))

    if str(evaluation_run.status) != SUCCESSFUL_EVALUATION_STATUS:
        raise RuntimeError(f"Foundry trace evaluation ended with status: {evaluation_run.status}")
    expected_total = len(conversation_ids)
    if (
        result_counts["total"] != expected_total
        or result_counts["passed"] != expected_total
        or result_counts["failed"] != 0
        or result_counts["errored"] != 0
        or result_counts["skipped"] != 0
    ):
        raise RuntimeError(f"Foundry trace evaluation did not pass: {result_counts}")
    expected_criterion_total = expected_total * len(evaluators)
    if (
        criterion_result_counts["total"] != expected_criterion_total
        or criterion_result_counts["passed"] != expected_criterion_total
        or criterion_result_counts["failed"] != 0
        or criterion_result_counts["errored"] != 0
        or criterion_result_counts["skipped"] != 0
    ):
        raise RuntimeError(
            f"Foundry trace evaluation criteria did not pass: {criterion_result_counts}"
        )


if __name__ == "__main__":
    run()
