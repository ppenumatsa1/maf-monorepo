from app.core.config import load_settings
from app.infrastructure.persistence.checkpoint_store import PostgresCheckpointStore
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.maf.workflows.underwriting import build_underwriting_workflow
from sqlalchemy import create_engine


def test_underwriting_master_workflow_uses_direct_check_executors() -> None:
    engine = create_engine("sqlite:///:memory:")
    workflow = build_underwriting_workflow(
        repository=WorkflowRunRepository(engine),
        settings=load_settings(),
        checkpoint_storage=PostgresCheckpointStore(engine),
        foundry_client=None,
    )

    assert workflow.name == "insurance-underwriting-workflow"
    assert set(workflow.executors) == {
        "init_context",
        "risk_score",
        "credit_check",
        "medical_check",
        "driving_check",
        "fan_in_aggregator",
        "final_decision",
    }
    assert all(
        executor.__class__.__name__ != "WorkflowExecutor"
        for executor in workflow.executors.values()
    )

    graph = workflow.graph_signature["edge_groups"]
    fan_out = next(group for group in graph if group["group_type"] == "FanOutEdgeGroup")
    assert fan_out["sources"] == ["init_context"]
    assert fan_out["targets"] == [
        "credit_check",
        "driving_check",
        "medical_check",
        "risk_score",
    ]

    fan_in_edges = {
        (edge["source"], edge["target"])
        for group in graph
        if group["group_type"] == "SingleEdgeGroup"
        for edge in group["edges"]
    }
    assert {
        ("risk_score", "fan_in_aggregator"),
        ("credit_check", "fan_in_aggregator"),
        ("medical_check", "fan_in_aggregator"),
        ("driving_check", "fan_in_aggregator"),
        ("fan_in_aggregator", "final_decision"),
    } <= fan_in_edges
