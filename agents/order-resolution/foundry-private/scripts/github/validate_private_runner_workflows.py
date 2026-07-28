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
    require(text, "secrets.POSTGRES_ADMIN_PASSWORD", name)
    if text.count("secrets.") != 1:
        raise AssertionError(
            f"{name} may reference only the PostgreSQL admin password secret."
        )
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
    require(deploy, "make foundry-project-connections", deploy_name)
    require(deploy, "make foundry-deploy", deploy_name)
    require(deploy, "make foundry-connectivity-proof", deploy_name)
    require(deploy, "make foundry-postgres-lockdown", deploy_name)
    require(deploy, "make foundry-evidence", deploy_name)
    require(deploy, "uses: actions/setup-python@v5", deploy_name)
    require(deploy, 'python-version: "3.12"', deploy_name)
    require(
        deploy,
        "Refresh federated Azure identity before hosted-agent release",
        deploy_name,
    )
    require_order(
        deploy,
        (
            "Refresh federated Azure identity before hosted-agent release",
            "Synchronize Foundry hosted-agent deployment role",
            "make foundry-deploy",
        ),
        deploy_name,
    )
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
            "make foundry-project-connections",
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
            "$(MAKE) foundry-project-connections",
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

    access_path_body = makefile.split("foundry-access-path:\n", maxsplit=1)[1].split(
        "\n\nclean:", maxsplit=1
    )[0]
    require(
        access_path_body,
        "RUNNER_SSH_PUBKEY_PATH is required",
        "foundry-access-path Make target",
    )
    require(
        access_path_body,
        'azd env select "$${FOUNDRY_AZD_ENV_NAME:-foundry-private-env}" --no-prompt',
        "foundry-access-path Make target",
    )
    require(
        access_path_body,
        "AZURE_DEV_USER_AGENT=microsoft_foundry_skill $(MAKE) -C ../.. foundry-preflight",
        "foundry-access-path Make target",
    )
    for value in (
        "azd env set CREATE_PRIVATE_RUNNER_ACCESS true",
        "azd env set CREATE_RUNNER_VM true",
        "azd env set MANAGE_PROJECT_CONNECTIONS false",
        "azd env set RUNNER_VM_SSH_PUBLIC_KEY",
        "azd provision --no-prompt",
        "AZURE_DEV_USER_AGENT=microsoft_foundry_skill",
    ):
        require(access_path_body, value, "foundry-access-path Make target")
    forbid(
        access_path_body,
        "iac/access-path.bicep",
        "foundry-access-path Make target",
    )
    forbid(access_path_body, "FOUNDRY_ACCESS_RG", "foundry-access-path Make target")
    foundry_up_body = makefile.split("foundry-up:\n", maxsplit=1)[1].split(
        "\n\nfoundry-preflight:", maxsplit=1
    )[0]
    require(foundry_up_body, "$(MAKE) foundry-provision", "foundry-up Make target")
    require(
        foundry_up_body,
        "$(MAKE) foundry-project-connections",
        "foundry-up Make target",
    )
    forbid(foundry_up_body, "azd up --no-prompt", "foundry-up Make target")

    register_runner = (
        Path(PRIVATE_PREFIX) / "scripts/github/register_vm_runner.sh"
    ).read_text()
    require(
        register_runner,
        'RUNNER_LABEL="${RUNNER_LABEL:-foundry-private-v2}"',
        "register_vm_runner.sh",
    )
    main_bicep = (
        Path(PRIVATE_PREFIX) / "infra/foundry-hosted/iac/main.bicep"
    ).read_text()
    require(
        main_bicep,
        "param restoreFoundryAccount bool = true",
        "private Foundry Bicep",
    )
    require(
        main_bicep,
        "Microsoft.CognitiveServices/accounts@2025-06-01",
        "private Foundry Bicep",
    )
    require(
        main_bicep,
        "restoreFoundryAccount ? {\n    restore: true\n  } : {}",
        "private Foundry Bicep",
    )
    require(
        main_bicep,
        "var resolvedProjectPrincipalId = foundryProject.identity.principalId",
        "private Foundry Bicep",
    )
    require(
        main_bicep,
        "if (manageProjectConnections && !empty(runtimeDatabaseUrl))",
        "private Foundry Bicep",
    )
    require(
        main_bicep,
        "module addProjectCapabilityHost './modules/add-project-capability-host.bicep' = if (createProjectCapabilityHost && manageProjectConnections)",
        "private Foundry Bicep",
    )
    for dependency in (
        "storageAccountRoleAssignment",
        "storageAccountRoleAssignmentFoundryAccountIdentity",
        "cosmosAccountRoleAssignments",
        "aiSearchRoleAssignments",
    ):
        require(main_bicep, dependency, "private Foundry Bicep")

    main_parameters = (
        Path(PRIVATE_PREFIX) / "infra/foundry-hosted/iac/main.parameters.json"
    ).read_text()
    require(
        main_parameters,
        '"restoreFoundryAccount": {\n      "value": "${RESTORE_FOUNDRY_ACCOUNT}"',
        "private Foundry Bicep parameters",
    )
    azd_defaults = (
        Path(PRIVATE_PREFIX) / "scripts/foundry/ensure_foundry_azd_defaults.sh"
    ).read_text()
    require(
        azd_defaults,
        'set_if_missing RESTORE_FOUNDRY_ACCOUNT "${RESTORE_FOUNDRY_ACCOUNT:-$restore_foundry_account_default}"',
        "private AZD defaults",
    )
    require(
        azd_defaults,
        'cleared RESTORE_FOUNDRY_ACCOUNT because $foundry_account_name is active',
        "private AZD defaults",
    )
    require(
        access_path_body,
        "../../scripts/foundry/ensure_foundry_azd_defaults.sh",
        "foundry-access-path Make target",
    )

    core_provision_body = makefile.split("foundry-provision:\n", maxsplit=1)[1].split(
        "\n\nfoundry-project-connections:", maxsplit=1
    )[0]
    require(
        core_provision_body,
        "azd env set MANAGE_PROJECT_CONNECTIONS false",
        "foundry-provision Make target",
    )
    connection_provision_body = makefile.split(
        "foundry-project-connections:\n", maxsplit=1
    )[1].split("\n\nfoundry-deploy:", maxsplit=1)[0]
    require(
        connection_provision_body,
        "azd env set MANAGE_PROJECT_CONNECTIONS true",
        "foundry-project-connections Make target",
    )
    require(
        connection_provision_body,
        "azd provision --no-prompt",
        "foundry-project-connections Make target",
    )

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
