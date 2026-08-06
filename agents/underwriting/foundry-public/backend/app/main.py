from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from dataclasses import asdict
from typing import Any

from app.core.config import load_settings
from app.core.observability import configure_observability
from app.modules.underwriting.models import FinalDecisionResult, UnderwritingApplication
from app.modules.underwriting.service import UnderwritingService


def _service() -> UnderwritingService:
    settings = load_settings()
    configure_observability(settings.log_level)
    return UnderwritingService(settings)


async def run_workflow(
    workflow_run_id: str | None = None,
    app: UnderwritingApplication | None = None,
    fail_risk_once: bool | None = None,
    fail_credit_randomly: bool | None = None,
    crash_after_executor: str | None = None,
) -> tuple[str, list[Any]]:
    service = _service()
    return await service.run_workflow(
        workflow_run_id=workflow_run_id,
        application=app or service.default_application(),
        fail_risk_once=fail_risk_once,
        fail_credit_randomly=fail_credit_randomly,
        crash_after_executor=crash_after_executor,
    )


async def resume_workflow(workflow_run_id: str) -> list[Any]:
    service = _service()
    return await service.resume_workflow(workflow_run_id)


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, default=str))


def _serialize_outputs(outputs: list[Any]) -> list[Any]:
    printable = []
    for output in outputs:
        if isinstance(output, FinalDecisionResult):
            printable.append(output.to_dict())
        elif hasattr(output, "to_dict"):
            printable.append(output.to_dict())
        elif hasattr(output, "__dict__"):
            printable.append(asdict(output))
        else:
            printable.append(str(output))
    return printable


def _cmd_db_reset() -> int:
    _service().reset_database()
    print("database reset complete")
    return 0


def _cmd_run() -> int:
    run_id = f"run-{uuid.uuid4().hex[:10]}"
    try:
        run_id, outputs = asyncio.run(run_workflow(workflow_run_id=run_id))
    except Exception as exc:
        print(f"RUN_ID={run_id}", file=sys.stderr)
        print(f"workflow crashed. run_id may be resumable. error={exc}", file=sys.stderr)
        return 1
    print(f"RUN_ID={run_id}")
    _print_json({"run_id": run_id, "outputs": _serialize_outputs(outputs)})
    return 0


def _cmd_resume(run_id: str) -> int:
    try:
        outputs = asyncio.run(resume_workflow(run_id))
    except Exception as exc:
        print(f"resume failed for run_id={run_id}. error={exc}", file=sys.stderr)
        return 1
    _print_json({"run_id": run_id, "resumed_outputs": _serialize_outputs(outputs)})
    return 0


def _cmd_state(run_id: str) -> int:
    _print_json(_service().get_state(run_id))
    return 0


def _cmd_events(run_id: str) -> int:
    _print_json(_service().get_events(run_id))
    return 0


def _cmd_checkpoints(run_id: str) -> int:
    _print_json(_service().get_checkpoints(run_id))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Insurance underwriting prototype using Microsoft Agent Framework"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run")
    sub.add_parser("db-reset")
    resume = sub.add_parser("resume")
    resume.add_argument("--run-id", required=True)
    state = sub.add_parser("state")
    state.add_argument("--run-id", required=True)
    events = sub.add_parser("events")
    events.add_argument("--run-id", required=True)
    checkpoints = sub.add_parser("checkpoints")
    checkpoints.add_argument("--run-id", required=True)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    if args.command == "run":
        return _cmd_run()
    if args.command == "db-reset":
        return _cmd_db_reset()
    if args.command == "resume":
        return _cmd_resume(args.run_id)
    if args.command == "state":
        return _cmd_state(args.run_id)
    if args.command == "events":
        return _cmd_events(args.run_id)
    if args.command == "checkpoints":
        return _cmd_checkpoints(args.run_id)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
