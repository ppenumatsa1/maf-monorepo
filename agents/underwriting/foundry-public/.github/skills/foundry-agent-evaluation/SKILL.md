---
name: foundry-agent-evaluation
description: Run the underwriting hosted trace evaluation, publish evidence, and enforce report-only evaluation guardrails.
---

# Foundry Agent Evaluation Skill

Use this skill for hosted workflow, release, or telemetry changes that need Foundry quality evidence.

## Scope

- Canonical dataset: `backend/.foundry/datasets/underwriting-smoke.jsonl`
- Declarative config: `backend/eval.yaml`
- Evaluation runner: `backend/evals/foundry_trace_eval.py`
- Evidence inputs and outputs:
  - `backend/.foundry/results/hosted-smoke-evidence.json`
  - `backend/.foundry/results/foundry-trace-eval.json`

## Execution model

1. Refresh live hosted evidence when needed:

```bash
make foundry-smoke
```

2. Run the supported report-only trace evaluation:

```bash
make foundry-eval
```

`make foundry-trace-eval` is the same supported gate. `make foundry-native-eval` is diagnostic only and must not replace this flow.

## Guardrails

- Keep one source-controlled smoke dataset under `backend/.foundry/datasets/`.
- Keep evaluation report-only unless repository policy explicitly changes.
- Evaluate only safe hosted conversation ids captured in the evidence file.
- The `invoke_agent` span must contain `gen_ai.input.messages` and
  `gen_ai.output.messages` in the OpenTelemetry GenAI message format. Emit
  only a redacted release summary (action, terminal status, and decision);
  never serialize applicant input, model rationale, or workflow payloads.
- Do not treat generated reports as business truth; use them as release evidence.
- Keep evaluation outputs free of applicant content and secrets.

## Concurrency

- Start `make foundry-eval` immediately after smoke evidence exists.
- It may run in parallel with `make foundry-hosted-e2e`; the two gates use
  separate evidence files and do not modify shared deployment state.
- Do not start telemetry validation until deployed E2E writes its evidence.

## Required evidence

- `backend/.foundry/results/hosted-smoke-evidence.json`
- `backend/.foundry/results/foundry-trace-eval.json`
