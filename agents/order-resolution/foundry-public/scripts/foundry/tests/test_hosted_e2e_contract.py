from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/foundry/hosted_e2e.sh"


def test_hosted_e2e_uses_azd_conversation_ids_and_postgres_state() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "extract_conversation_id" in source
    assert "Conversation:" in source
    assert "RUNTIME_DATABASE_URL" in source
    assert "psql" in source
    assert "SELECT status FROM workflow_runs" in source
    assert "SELECT checkpoint_id::text FROM approvals" in source
    assert "SELECT COUNT(*) FROM workflow_events" in source
    assert "extract_json_output" not in source
    assert "pending_approvals" not in source
    assert "(.events // [])" not in source


def test_hosted_e2e_emits_fresh_release_window_conversation_evidence() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert 'release_id="${FOUNDRY_RELEASE_ID:-manual-hosted-e2e}"' in source
    assert 'release_started_at="${FOUNDRY_RELEASE_STARTED_AT:-$STARTED_AT}"' in source
    assert "conversation_ids:" in source
    assert "low_risk_thread_id:" in source
    assert "high_risk_thread_id:" in source
    assert "damaged_item_thread_id:" in source
    assert source.count('terminal_status: "completed"') == 3


def test_hosted_e2e_structured_resume_fails_auth_without_retrying() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "Authorization: Bearer $token" in source
    assert "^(404|409|429|5[0-9][0-9])$" in source
    assert "401|403" not in source


def test_hosted_e2e_accepts_structured_azd_responses() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "response_status" in source
    assert "response_message" in source
    assert "'.status // empty'" in source
    assert "'.message // .latest_output.message // empty'" in source
    assert '"$(response_status "$first_turn")" != "completed"' in source
    assert "prior request was|previous result" in source


def test_hosted_e2e_records_approved_outcomes_in_conversation_traces() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert source.count("Why was that approved resolution selected?") == 2
    assert "High-risk post-approval explanation changed persisted terminal state." in source
    assert "Damaged-item post-approval explanation changed persisted terminal state." in source
