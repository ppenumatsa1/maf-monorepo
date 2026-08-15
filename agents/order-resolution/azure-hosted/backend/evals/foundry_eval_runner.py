from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
import yaml
from app.maf.clients import get_foundry_models_config
from azure.ai.projects.aio import AIProjectClient
from azure.identity.aio import DefaultAzureCredential


def _read_eval_config(path: Path) -> dict[str, object]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("backend/eval.yaml must be a mapping")
    return config


def _load_report_cases(dataset_path: Path, case_ids: list[str]) -> list[dict[str, str]]:
    rows_by_case_id: dict[str, dict[str, str]] = {}
    for line_number, line in enumerate(
        dataset_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        row = json.loads(line)
        case_id = row.get("id")
        query = row.get("input")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(f"{dataset_path}:{line_number} must contain a non-empty id")
        if not isinstance(query, str) or not query.strip():
            raise ValueError(f"{dataset_path}:{line_number} must contain a non-empty input")
        rows_by_case_id[case_id] = {"id": case_id.strip(), "input": query.strip()}

    missing_case_ids = [case_id for case_id in case_ids if case_id not in rows_by_case_id]
    if missing_case_ids:
        raise ValueError(
            f"Foundry report case IDs are missing from {dataset_path}: {', '.join(missing_case_ids)}"
        )
    return [rows_by_case_id[case_id] for case_id in case_ids]


def _load_report_queries(dataset_path: Path, case_ids: list[str]) -> list[str]:
    return [row["input"] for row in _load_report_cases(dataset_path, case_ids)]


def _to_jsonable(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    if hasattr(value, "model_dump"):
        return _to_jsonable(value.model_dump())
    if hasattr(value, "dict"):
        return _to_jsonable(value.dict())
    return str(value)


def _normalize_result_counts(result_counts: object) -> dict[str, object]:
    jsonable = _to_jsonable(result_counts)
    if isinstance(jsonable, dict):
        return {str(key): value for key, value in jsonable.items()}
    return {}


def _count_blocking_result_rows(result_counts: dict[str, object]) -> int:
    total = 0
    for key, value in result_counts.items():
        normalized_key = str(key).lower()
        if "fail" not in normalized_key and "error" not in normalized_key:
            continue
        if isinstance(value, bool):
            total += int(value)
        elif isinstance(value, (int, float)):
            total += int(value)
        elif isinstance(value, str) and value.isdigit():
            total += int(value)
    return total


def _normalize_status(value: object) -> str:
    raw = getattr(value, "value", value)
    text = str(raw).strip()
    if "." in text:
        candidate = text.rsplit(".", 1)[-1]
        if candidate:
            text = candidate
    return text.lower()


def _release_eval_passed(
    *, run_status: str, result_counts: dict[str, object], captures: Sequence[dict[str, object]]
) -> bool:
    if run_status != "completed":
        return False
    if _count_blocking_result_rows(result_counts) != 0:
        return False
    return all(capture.get("terminal_status") == "completed" for capture in captures)


def _workflow_run_id(events: Sequence[dict[str, object]]) -> str:
    workflow_run_ids = sorted(
        {
            str(event.get("payload", {}).get("workflow_run_id"))
            for event in events
            if isinstance(event, dict)
            and isinstance(event.get("payload"), dict)
            and event.get("payload", {}).get("workflow_run_id")
        }
    )
    if len(workflow_run_ids) != 1:
        raise RuntimeError(f"Expected exactly one workflow_run_id, found {workflow_run_ids!r}.")
    return workflow_run_ids[0]


def _release_target_payload(api_url: str) -> dict[str, object]:
    payload: dict[str, object] = {"api_url": api_url}
    if environment := os.getenv("AZURE_ENV_NAME"):
        payload["azd_env_name"] = environment
    if subscription_id := os.getenv("AZURE_SUBSCRIPTION_ID"):
        payload["subscription_id"] = subscription_id
    if resource_group := os.getenv("AZURE_RESOURCE_GROUP"):
        payload["resource_group"] = resource_group
    if location := os.getenv("AZURE_LOCATION"):
        payload["location"] = location
    return payload


async def _capture_app_outputs(
    cases: Sequence[dict[str, str]], api_url: str
) -> list[dict[str, str]]:
    captures: list[dict[str, str]] = []
    release_id = os.getenv("RELEASE_ID") or os.getenv("RELEASE_RUN_ID") or "local"

    async with httpx.AsyncClient(base_url=api_url.rstrip("/"), timeout=90.0) as client:
        for case in cases:
            case_id = case["id"]
            query = case["input"]
            requested_thread_id = f"foundry-eval-{release_id}-{case_id}-{uuid4().hex[:8]}"
            run = (
                (
                    await client.post(
                        "/api/chat/run",
                        json={
                            "thread_id": requested_thread_id,
                            "message": query,
                            "customer_id": "foundry-evaluation",
                            "session_id": f"foundry-eval-{uuid4()}",
                        },
                    )
                )
                .raise_for_status()
                .json()
            )
            thread_id = str(run["thread_id"])
            for _ in range(90):
                details = (
                    (await client.get(f"/api/workflows/{thread_id}")).raise_for_status().json()
                )
                if details.get("status") == "waiting_approval":
                    pending = details.get("pending_approvals") or []
                    if not pending:
                        raise RuntimeError(
                            f"Workflow {thread_id} is waiting without an approval request."
                        )
                    (
                        await client.post(
                            "/api/hitl/respond",
                            json={
                                "checkpoint_id": pending[0]["checkpoint_id"],
                                "decision": "approve",
                                "reviewer": "foundry-evaluation",
                                "comments": f"Automated evaluation approval for {case_id}",
                            },
                        )
                    ).raise_for_status()
                elif details.get("status") in {"completed", "escalated"}:
                    latest_output = details.get("latest_output") or {}
                    terminal_status = str(
                        latest_output.get("status") or details.get("status") or ""
                    )
                    events = (
                        (
                            await client.get(
                                f"/api/workflows/{thread_id}/events", params={"limit": 100}
                            )
                        )
                        .raise_for_status()
                        .json()
                    )
                    captures.append(
                        {
                            "scenario_id": case_id,
                            "thread_id": thread_id,
                            "workflow_run_id": _workflow_run_id(events.get("items", [])),
                            "query": query,
                            "response": str(latest_output.get("message", "")),
                            "terminal_status": terminal_status,
                        }
                    )
                    if terminal_status != "completed":
                        raise RuntimeError(
                            f"Workflow {thread_id} ended with terminal status {terminal_status!r}."
                        )
                    break
                elif details.get("status") == "failed":
                    raise RuntimeError(f"Workflow {thread_id} failed during evaluation capture.")
                await asyncio.sleep(1)
            else:
                raise TimeoutError(
                    f"Workflow {thread_id} did not complete during evaluation capture."
                )

    return captures


def _build_release_artifact(
    *,
    release_id: str,
    release_started_at: str,
    api_url: str,
    provider_status: str,
    case_ids: Sequence[str],
    evaluators: Sequence[str],
    result_counts: dict[str, object],
    captures: Sequence[dict[str, object]],
    http_output_capture: str,
    eval_id: str | None,
    run_id: str | None,
    report_url: str | None,
    error: object,
) -> dict[str, object]:
    status = (
        "passed"
        if _release_eval_passed(
            run_status=provider_status,
            result_counts=result_counts,
            captures=captures,
        )
        else "failed"
    )
    return {
        "schema_version": 1,
        "contract": "azure-hosted-release/v1",
        "lane": "azure-hosted",
        "artifact_type": "evaluation",
        "status": status,
        "release_id": release_id,
        "release_started_at": release_started_at,
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "target": _release_target_payload(api_url),
        "provider": "foundry",
        "run_status": provider_status,
        "provider_status": provider_status,
        "case_ids": list(case_ids),
        "query_count": len(case_ids),
        "evaluators": list(evaluators),
        "result_counts": result_counts,
        "blocking_result_rows": _count_blocking_result_rows(result_counts),
        "captures": [_to_jsonable(item) for item in captures],
        "http_output_capture": http_output_capture,
        "eval_id": eval_id,
        "run_id": run_id,
        "report_url": report_url,
        "error": _to_jsonable(error),
    }


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_to_jsonable(payload), indent=2) + "\n", encoding="utf-8")


async def run_foundry_eval() -> None:
    root = Path(__file__).resolve().parents[1]
    foundry_root = root / ".foundry"
    config = _read_eval_config(root / "eval.yaml")

    dataset = config.get("dataset")
    if not isinstance(dataset, dict):
        raise ValueError("backend/eval.yaml is missing dataset mapping")
    local_uri = dataset.get("local_uri")
    if not isinstance(local_uri, str) or not local_uri.strip():
        raise ValueError("backend/eval.yaml dataset.local_uri is required")

    dataset_path = root / local_uri
    foundry_cfg = config.get("foundry")
    if not isinstance(foundry_cfg, dict):
        raise ValueError("backend/eval.yaml is missing foundry config block")

    eval_name = str(foundry_cfg.get("name", "order-resolution-foundry-report"))
    report_case_ids_raw = foundry_cfg.get("report_case_ids", [])
    if (
        not isinstance(report_case_ids_raw, list)
        or not report_case_ids_raw
        or not all(isinstance(case_id, str) and case_id for case_id in report_case_ids_raw)
    ):
        raise ValueError("backend/eval.yaml foundry.report_case_ids must be a non-empty list")
    report_case_ids = [str(case_id) for case_id in report_case_ids_raw]
    if len(set(report_case_ids)) != len(report_case_ids):
        raise ValueError("backend/eval.yaml foundry.report_case_ids must not contain duplicates")
    selected_cases = _load_report_cases(dataset_path, report_case_ids)

    evaluators_raw = foundry_cfg.get("evaluators", [])
    if not isinstance(evaluators_raw, list) or not all(
        isinstance(name, str) and name for name in evaluators_raw
    ):
        raise ValueError("backend/eval.yaml foundry.evaluators must be a list of evaluator names")
    evaluators = [str(name) for name in evaluators_raw]
    poll_interval = float(
        os.getenv("FOUNDRY_EVAL_POLL_INTERVAL", foundry_cfg.get("poll_interval", 5.0))
    )
    timeout = float(os.getenv("FOUNDRY_EVAL_TIMEOUT", foundry_cfg.get("timeout", 300.0)))
    api_url = os.getenv("FOUNDRY_EVAL_API_URL", "http://localhost:8000")
    release_id = os.getenv("RELEASE_ID") or os.getenv("RELEASE_RUN_ID")
    release_started_at = os.getenv("RELEASE_STARTED_AT") or os.getenv("RELEASE_E2E_STARTED_AT")

    report_path = foundry_root / "results" / "foundry-report.json"
    capture_path = Path(
        os.getenv(
            "FOUNDRY_EVAL_CAPTURE_FILE",
            str(foundry_root / "results" / "foundry-http-output.json"),
        )
    )
    release_output_file = os.getenv("FOUNDRY_EVAL_OUTPUT_FILE")

    captures: list[dict[str, object]] = []
    result_counts: dict[str, object] = {}
    provider_status = "failed"
    report_url: str | None = None
    eval_id: str | None = None
    run_id: str | None = None
    raw_payload: dict[str, object] = {
        "status": provider_status,
        "provider": "foundry",
        "case_ids": report_case_ids,
        "query_count": len(selected_cases),
        "evaluators": evaluators,
        "api_url": api_url,
        "result_counts": result_counts,
        "captures": captures,
        "capture_path": str(capture_path),
    }

    try:
        models_cfg = get_foundry_models_config()
        if models_cfg is None:
            raise RuntimeError(
                "Foundry model configuration is missing. Set FOUNDRY_PROJECTS_ENDPOINT and "
                "FOUNDRY_MODEL_DEPLOYMENT_NAME."
            )
        judge_model = os.getenv("FOUNDRY_EVAL_MODEL", models_cfg.model)
        credential = DefaultAzureCredential()
        project_client = AIProjectClient(
            endpoint=models_cfg.project_endpoint, credential=credential
        )
        openai_client = project_client.get_openai_client()

        captures = await _capture_app_outputs(selected_cases, api_url)
        _write_json(
            capture_path,
            {
                "provider": "http",
                "target": _release_target_payload(api_url),
                "case_ids": report_case_ids,
                "captures": captures,
            },
        )

        testing_criteria = [
            {
                "type": "azure_ai_evaluator",
                "name": evaluator_name,
                "evaluator_name": f"builtin.{evaluator_name}",
                "initialization_parameters": {"deployment_name": judge_model},
                "data_mapping": {
                    "query": "{{item.query}}",
                    "response": "{{item.response}}",
                },
            }
            for evaluator_name in evaluators
        ]

        eval_object = await openai_client.evals.create(
            name=eval_name,
            data_source_config={
                "type": "custom",
                "item_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "response": {"type": "string"},
                    },
                    "required": ["query", "response"],
                },
                "include_sample_schema": True,
            },
            testing_criteria=testing_criteria,
        )

        eval_run = await openai_client.evals.runs.create(
            eval_id=eval_object.id,
            name=f"{eval_name} Run",
            data_source={
                "type": "jsonl",
                "source": {
                    "type": "file_content",
                    "content": [
                        {
                            "item": {
                                "query": str(capture["query"]),
                                "response": str(capture["response"]),
                            },
                            "sample": {"id": str(capture["scenario_id"])},
                        }
                        for capture in captures
                    ],
                },
            },
        )

        start = asyncio.get_running_loop().time()
        while _normalize_status(eval_run.status) not in {"completed", "failed", "cancelled"}:
            if asyncio.get_running_loop().time() - start > timeout:
                raise TimeoutError(f"Foundry eval run timed out after {timeout} seconds")
            await asyncio.sleep(poll_interval)
            eval_run = await openai_client.evals.runs.retrieve(
                run_id=eval_run.id,
                eval_id=eval_object.id,
            )

        provider_status = _normalize_status(eval_run.status)
        result_counts = _normalize_result_counts(getattr(eval_run, "result_counts", None))
        eval_id = getattr(eval_object, "id", None)
        run_id = getattr(eval_run, "id", None)
        report_url = f"{models_cfg.project_endpoint.rstrip('/')}/evaluation/evaluations/{eval_id}/runs/{run_id}"
        raw_payload = {
            "status": provider_status,
            "provider": "foundry",
            "eval_id": eval_id,
            "run_id": run_id,
            "case_ids": report_case_ids,
            "query_count": len(selected_cases),
            "evaluators": evaluators,
            "result_counts": result_counts,
            "captures": captures,
            "capture_path": str(capture_path),
            "report_url": report_url,
            "error": _to_jsonable(getattr(eval_run, "error", None)),
        }
    except Exception as exc:  # noqa: BLE001
        provider_status = (
            "timeout"
            if isinstance(exc, TimeoutError)
            else str(raw_payload.get("status") or "failed")
        )
        raw_payload["status"] = provider_status
        raw_payload["error"] = str(exc)
        raw_payload["result_counts"] = result_counts
        raw_payload["captures"] = captures
        raw_payload["capture_path"] = str(capture_path)
        if "eval_object" in locals():
            eval_id = getattr(eval_object, "id", None)
            raw_payload["eval_id"] = eval_id
        if "eval_run" in locals():
            run_id = getattr(eval_run, "id", None)
            raw_payload["run_id"] = run_id
            raw_payload["run_status"] = _normalize_status(getattr(eval_run, "status", "unknown"))
            provider_status = raw_payload["run_status"]
        if eval_id and run_id and "models_cfg" in locals():
            report_url = f"{models_cfg.project_endpoint.rstrip('/')}/evaluation/evaluations/{eval_id}/runs/{run_id}"
            raw_payload["report_url"] = report_url
    finally:
        if "openai_client" in locals():
            await openai_client.close()
        if "project_client" in locals():
            await project_client.close()
        if "credential" in locals():
            await credential.close()

    _write_json(report_path, raw_payload)

    if release_output_file:
        if not release_id or not release_started_at:
            raise RuntimeError(
                "RELEASE_ID and RELEASE_STARTED_AT are required when FOUNDRY_EVAL_OUTPUT_FILE is set."
            )
        release_payload = _build_release_artifact(
            release_id=release_id,
            release_started_at=release_started_at,
            api_url=api_url,
            provider_status=provider_status,
            case_ids=report_case_ids,
            evaluators=evaluators,
            result_counts=result_counts,
            captures=captures,
            http_output_capture=os.path.relpath(capture_path, Path(release_output_file).parent),
            eval_id=eval_id,
            run_id=run_id,
            report_url=report_url,
            error=raw_payload.get("error"),
        )
        _write_json(Path(release_output_file), release_payload)

    print(json.dumps(raw_payload, indent=2))
    print(f"Foundry report saved to: {report_path}")
    if capture_path.exists():
        print(f"HTTP output capture saved to: {capture_path}")

    enforce_pass = os.getenv("FOUNDRY_EVAL_ENFORCE_PASS", "false").lower() in {"1", "true", "yes"}
    if enforce_pass and not _release_eval_passed(
        run_status=provider_status,
        result_counts=result_counts,
        captures=captures,
    ):
        raise RuntimeError(
            "Foundry eval gate failed: run_status must be completed, captured scenarios must "
            "complete, and failed/errored result counts must be zero."
        )


if __name__ == "__main__":
    asyncio.run(run_foundry_eval())
