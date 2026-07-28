#!/usr/bin/env python3
"""Validate the static safety contract for private-runner GitHub workflows."""

from __future__ import annotations

from pathlib import Path


WORKFLOWS = Path(".github/workflows")
DEPLOYMENT_WORKFLOWS = (
    "order-resolution-private-provision.yml",
    "order-resolution-private-deploy.yml",
)
SERIALIZED_PRIVATE_WORKFLOWS = (
    *DEPLOYMENT_WORKFLOWS,
    "order-resolution-private-observability.yml",
)
PRIVATE_PREFIX = "agents/order-resolution/foundry-private"
EXPECTED_TARGETS = (
    "AZD_ENVIRONMENT_NAME: foundry-private-env",
    "TARGET_RESOURCE_GROUP: rg-maf-ora-foundry-v2",
    "TARGET_FOUNDRY_PROJECT: order-resolution",
    "TARGET_POSTGRES_DATABASE: maf_workflow",
)


def require(text: str, value: str, workflow: str) -> None:
    if value not in text:
        raise AssertionError(f"{workflow} is missing required contract: {value}")


def forbid(text: str, value: str, workflow: str) -> None:
    if value in text:
        raise AssertionError(f"{workflow} contains forbidden contract: {value}")


def require_order(text: str, values: tuple[str, ...], source: str) -> None:
    positions = [text.index(value) if value in text else -1 for value in values]
    if -1 in positions or positions != sorted(positions):
        raise AssertionError(
            f"{source} does not preserve the required release order: "
            f"{' -> '.join(values)}"
        )


def validate_deployment_workflow(name: str) -> None:
    text = (WORKFLOWS / name).read_text()
    require(text, "workflow_dispatch:", name)
    require(text, "confirmation:", name)
    require(text, "environment: foundry-private-env", name)
    require(text, "self-hosted", name)
    require(text, "foundry-private-v2", name)
    require(text, "id-token: write", name)
    require(text, "uses: azure/login@v2", name)
    require(text, "client-id: ${{ vars.AZURE_CLIENT_ID }}", name)
    require(text, "tenant-id: ${{ vars.AZURE_TENANT_ID }}", name)
    require(text, "subscription-id: ${{ vars.AZURE_SUBSCRIPTION_ID }}", name)
    require(text, "azd config set auth.useAzCliAuth true", name)
    require(
        text,
        f"{PRIVATE_PREFIX}/scripts/foundry/validate_private_runner_environment.sh",
        name,
    )
    require(
        text,
        f"git clean -ffdx -e {PRIVATE_PREFIX}/infra/foundry-hosted/.azure/",
        name,
    )
    forbid(text, "pull_request:", name)
    forbid(text, "push:", name)
    forbid(text, "workflow_call:", name)
    forbid(text, "secrets.", name)
    for target in EXPECTED_TARGETS:
        require(text, target, name)


def validate() -> None:
    for name in DEPLOYMENT_WORKFLOWS:
        validate_deployment_workflow(name)

    for name in SERIALIZED_PRIVATE_WORKFLOWS:
        require(
            (WORKFLOWS / name).read_text(),
            "group: order-resolution-private-release",
            name,
        )

    deploy_name = "order-resolution-private-deploy.yml"
    deploy = (WORKFLOWS / deploy_name).read_text()
    require(deploy, "make foundry-app-deploy", deploy_name)
    require(deploy, "make foundry-deploy", deploy_name)
    require(deploy, "make foundry-connectivity-proof", deploy_name)
    require(deploy, "make foundry-postgres-lockdown", deploy_name)
    require(deploy, "make foundry-evidence", deploy_name)
    require(deploy, "postgres_lockdown_confirmation:", deploy_name)
    require(
        deploy,
        "inputs.postgres_lockdown_confirmation == 'lockdown'",
        deploy_name,
    )
    require(
        deploy,
        "Verify active Container Apps use private ACR images",
        deploy_name,
    )
    forbid(deploy, "refresh_hosted_agent:", deploy_name)
    forbid(deploy, "repair_postgres_admin_password:", deploy_name)
    forbid(deploy, "run_smoke:", deploy_name)
    forbid(deploy, "run_evidence:", deploy_name)
    forbid(deploy, "make foundry-hosted-refresh", deploy_name)
    require_order(
        deploy,
        (
            "make foundry-app-deploy",
            "make foundry-deploy",
            "make foundry-connectivity-proof",
            "make foundry-postgres-lockdown",
            "make foundry-evidence",
        ),
        deploy_name,
    )

    makefile = (Path(PRIVATE_PREFIX) / "Makefile").read_text()
    release_body = makefile.split("foundry-release:\n", maxsplit=1)[1].split(
        "\n\nfoundry-smoke:", maxsplit=1
    )[0]
    require_order(
        release_body,
        (
            "$(MAKE) test",
            "$(MAKE) foundry-provision-preview",
            "$(MAKE) foundry-provision",
            "$(MAKE) foundry-app-deploy",
            "$(MAKE) foundry-deploy",
            "$(MAKE) foundry-connectivity-proof",
            "$(MAKE) foundry-postgres-lockdown",
            "$(MAKE) foundry-evidence",
        ),
        "foundry-release Make target",
    )
    forbid(release_body, "foundry-hosted-refresh", "foundry-release Make target")
    repair_script = (
        Path(PRIVATE_PREFIX)
        / "scripts/foundry/repair_private_postgres_admin_password.sh"
    )
    if repair_script.exists():
        raise AssertionError("Private release retains a PostgreSQL admin-password repair path.")

    provision_name = "order-resolution-private-provision.yml"
    provision = (WORKFLOWS / provision_name).read_text()
    require(provision, "make foundry-provision", provision_name)

    validation_name = "order-resolution-private-validation.yml"
    validation = (WORKFLOWS / validation_name).read_text()
    require(validation, "pull_request:", validation_name)
    require(validation, "runs-on: ubuntu-latest", validation_name)
    require(
        validation,
        f"python3 {PRIVATE_PREFIX}/scripts/github/validate_private_runner_workflows.py",
        validation_name,
    )
    forbid(validation, "id-token: write", validation_name)
    forbid(validation, "uses: azure/login@v2", validation_name)
    forbid(validation, "azd provision", validation_name)
    forbid(validation, "azd deploy", validation_name)


if __name__ == "__main__":
    validate()
    print("Private runner workflow static contracts passed.")
