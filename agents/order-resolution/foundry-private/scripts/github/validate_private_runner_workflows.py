#!/usr/bin/env python3
"""Validate the static safety contract for private-runner GitHub workflows."""

from __future__ import annotations

from pathlib import Path

WORKFLOWS = Path(".github/workflows")
DEPLOYMENT_WORKFLOWS = (
    "order-resolution-private-provision.yml",
    "order-resolution-private-deploy.yml",
)
PACKAGE_VALIDATION_WORKFLOW = "order-resolution-private-package-validation.yml"
EVIDENCE_WORKFLOW = "order-resolution-private-evidence.yml"
RUNNER_START_WORKFLOW = "order-resolution-private-runner-start.yml"
OBSERVABILITY_WORKFLOW = "order-resolution-private-observability.yml"
SERIALIZED_PRIVATE_WORKFLOWS = (
    *DEPLOYMENT_WORKFLOWS,
    PACKAGE_VALIDATION_WORKFLOW,
    EVIDENCE_WORKFLOW,
    OBSERVABILITY_WORKFLOW,
)
PRIVATE_DISPATCH_WORKFLOWS = (
    *SERIALIZED_PRIVATE_WORKFLOWS,
    RUNNER_START_WORKFLOW,
)
PRIVATE_PREFIX = "agents/order-resolution/foundry-private"
PROFILE_MIRROR_SCRIPT = (
    f"{PRIVATE_PREFIX}/scripts/github/validate_github_profile_mirror.sh"
)
EXPECTED_TARGET_MIRRORS = (
    "AZD_ENVIRONMENT_NAME: ${{ vars.AZURE_ENV_NAME }}",
    "TARGET_RESOURCE_GROUP: ${{ vars.AZURE_RESOURCE_GROUP }}",
    "TARGET_FOUNDRY_PROJECT: ${{ vars.FOUNDRY_PROJECT_NAME }}",
    "TARGET_POSTGRES_DATABASE: ${{ vars.POSTGRES_DATABASE_NAME }}",
    "PRIVATE_RUNNER_LABEL: ${{ vars.PRIVATE_RUNNER_LABEL }}",
    "PRIVATE_RUNNER_VM_NAME: ${{ vars.PRIVATE_RUNNER_VM_NAME }}",
)
FORBIDDEN_TARGET_LITERALS = (
    "rg-maf-ora-" + "foundry-v2",
    "rg-maf-ora-" + "foundry-private",
    "foundry-private-" + "env",
    "foundry-private-" + "v2",
    "vm-maffnd-" + "runner",
    "maf_" + "workflow",
    "7df95e88-701c-4693-" + "af77-3159f83b558d",
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
    require(text, "self-hosted", name)
    require(text, 'runs-on: [self-hosted, "${{ vars.PRIVATE_RUNNER_LABEL }}"]', name)
    require(text, "id-token: write", name)
    require(text, "uses: azure/login@v2", name)
    require(text, "client-id: ${{ vars.AZURE_CLIENT_ID }}", name)
    require(text, "tenant-id: ${{ vars.AZURE_TENANT_ID }}", name)
    require(text, "subscription-id: ${{ vars.AZURE_SUBSCRIPTION_ID }}", name)
    require(text, "azd config set auth.useAzCliAuth true", name)
    if name == "order-resolution-private-provision.yml":
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
    if name == "order-resolution-private-provision.yml":
        require(text, "secrets.POSTGRES_ADMIN_PASSWORD", name)
    if name == "order-resolution-private-provision.yml" and text.count("secrets.") != 1:
        raise AssertionError(
            f"{name} may reference only the PostgreSQL admin password secret."
        )
    if name == "order-resolution-private-deploy.yml" and "secrets." in text:
        raise AssertionError(
            f"{name} must not read secrets during an app-only private release."
        )
    require(text, PROFILE_MIRROR_SCRIPT, name)
    require_order(
        text,
        ("uses: actions/checkout@v4", PROFILE_MIRROR_SCRIPT, "uses: azure/login@v2"),
        name,
    )
    for target in EXPECTED_TARGET_MIRRORS:
        require(text, target, name)
    for literal in FORBIDDEN_TARGET_LITERALS:
        forbid(text, literal, name)


def validate() -> None:
    profile_mirror = Path(PROFILE_MIRROR_SCRIPT).read_text()
    for value in (
        "deployment/profile.sh",
        "deployment_profile_load",
        "deployment_profile_validate",
        "DEPLOYMENT_LANE",
        "AZURE_ENV_NAME",
        "AZURE_TENANT_ID",
        "AZURE_SUBSCRIPTION_ID",
        "AZURE_RESOURCE_GROUP",
        "FOUNDRY_PROJECT_NAME",
        "POSTGRES_DATABASE_NAME",
        "PRIVATE_RUNNER_LABEL",
        "PRIVATE_RUNNER_VM_NAME",
    ):
        require(profile_mirror, value, PROFILE_MIRROR_SCRIPT)
    if not (Path(PROFILE_MIRROR_SCRIPT).stat().st_mode & 0o111):
        raise AssertionError(f"{PROFILE_MIRROR_SCRIPT} must be executable")

    for name in PRIVATE_DISPATCH_WORKFLOWS:
        text = (WORKFLOWS / name).read_text()
        require(text, "workflow_dispatch:", name)
        forbid(text, "confirmation:", name)
        forbid(text, "inputs.confirmation", name)
        forbid(text, "environment:", name)
        for literal in FORBIDDEN_TARGET_LITERALS:
            forbid(text, literal, name)

    for name in SERIALIZED_PRIVATE_WORKFLOWS:
        text = (WORKFLOWS / name).read_text()
        require(text, PROFILE_MIRROR_SCRIPT, name)
        require_order(
            text,
            ("uses: actions/checkout@v4", PROFILE_MIRROR_SCRIPT, "uses: azure/login@v2"),
            name,
        )
        for target in EXPECTED_TARGET_MIRRORS:
            require(text, target, name)

    for name in DEPLOYMENT_WORKFLOWS:
        validate_deployment_workflow(name)

    runner_start_workflow = (WORKFLOWS / RUNNER_START_WORKFLOW).read_text()
    for value in (
        "runs-on: ubuntu-latest",
        "id-token: write",
        "az vm start",
        PROFILE_MIRROR_SCRIPT,
        "PowerState/running",
        "PRIVATE_RUNNER_LABEL: ${{ vars.PRIVATE_RUNNER_LABEL }}",
        "PRIVATE_RUNNER_VM_NAME: ${{ vars.PRIVATE_RUNNER_VM_NAME }}",
    ):
        require(runner_start_workflow, value, RUNNER_START_WORKFLOW)
    require_order(
        runner_start_workflow,
        ("uses: actions/checkout@v4", PROFILE_MIRROR_SCRIPT, "uses: azure/login@v2"),
        RUNNER_START_WORKFLOW,
    )
    for target in EXPECTED_TARGET_MIRRORS:
        require(runner_start_workflow, target, RUNNER_START_WORKFLOW)
    for literal in FORBIDDEN_TARGET_LITERALS:
        forbid(runner_start_workflow, literal, RUNNER_START_WORKFLOW)
    forbid(
        runner_start_workflow,
        "az vm run-command",
        RUNNER_START_WORKFLOW,
    )

    for name in SERIALIZED_PRIVATE_WORKFLOWS:
        require(
            (WORKFLOWS / name).read_text(),
            "group: order-resolution-private-release",
            name,
        )

    deploy_name = "order-resolution-private-deploy.yml"
    deploy = (WORKFLOWS / deploy_name).read_text()
    require(deploy, "make foundry-app-only-release", deploy_name)
    require(deploy, "uses: actions/setup-python@v5", deploy_name)
    require(deploy, 'python-version: "3.12"', deploy_name)
    require(
        deploy,
        "Validate existing private dependencies and deploy app-only release",
        deploy_name,
    )
    forbid(deploy, "refresh_hosted_agent:", deploy_name)
    forbid(deploy, "repair_postgres_admin_password:", deploy_name)
    forbid(deploy, "run_smoke:", deploy_name)
    forbid(deploy, "run_evidence:", deploy_name)
    forbid(deploy, "make foundry-hosted-refresh", deploy_name)
    forbid(deploy, "azd ext install", deploy_name)
    forbid(deploy, "bootstrap_private_azd_environment.sh", deploy_name)
    forbid(deploy, "ensure_foundry_azd_defaults.sh", deploy_name)
    forbid(deploy, "assign_private_foundry_project_manager.sh", deploy_name)
    forbid(deploy, "make foundry-provision", deploy_name)
    forbid(deploy, "make foundry-project-connections", deploy_name)
    forbid(deploy, "make foundry-deploy", deploy_name)
    forbid(deploy, "make foundry-connectivity-proof", deploy_name)
    forbid(deploy, "make foundry-postgres-lockdown", deploy_name)
    forbid(deploy, "make foundry-evidence", deploy_name)
    forbid(deploy, "\n  evidence:\n", deploy_name)

    package_validation = (WORKFLOWS / PACKAGE_VALIDATION_WORKFLOW).read_text()
    for value in (
        "workflow_dispatch:",
        "self-hosted",
        'runs-on: [self-hosted, "${{ vars.PRIVATE_RUNNER_LABEL }}"]',
        PROFILE_MIRROR_SCRIPT,
        "id-token: write",
        "uses: azure/login@v2",
        "client-id: ${{ vars.AZURE_CLIENT_ID }}",
        "tenant-id: ${{ vars.AZURE_TENANT_ID }}",
        "subscription-id: ${{ vars.AZURE_SUBSCRIPTION_ID }}",
        "azd config set auth.useAzCliAuth true",
        "make foundry-app-only-preflight",
        "./scripts/foundry/sync_hosted_source.sh",
        "azd package --no-prompt",
        f"git clean -ffdx -e {PRIVATE_PREFIX}/infra/foundry-hosted/.azure/",
    ):
        require(package_validation, value, PACKAGE_VALIDATION_WORKFLOW)
    for forbidden_operation in (
        "secrets.",
        "azd provision",
        "azd deploy",
        "make foundry-app-only-release",
        "make foundry-hosted-app-deploy",
        "make foundry-project-connections",
        "make foundry-postgres-lockdown",
        "make foundry-evidence",
    ):
        forbid(package_validation, forbidden_operation, PACKAGE_VALIDATION_WORKFLOW)

    evidence = (WORKFLOWS / EVIDENCE_WORKFLOW).read_text()
    for value in (
        "workflow_dispatch:",
        "self-hosted",
        'runs-on: [self-hosted, "${{ vars.PRIVATE_RUNNER_LABEL }}"]',
        PROFILE_MIRROR_SCRIPT,
        "id-token: write",
        "uses: azure/login@v2",
        "uses: actions/setup-python@v5",
        'python-version: "3.12"',
        "client-id: ${{ vars.AZURE_CLIENT_ID }}",
        "tenant-id: ${{ vars.AZURE_TENANT_ID }}",
        "subscription-id: ${{ vars.AZURE_SUBSCRIPTION_ID }}",
        "azd config set auth.useAzCliAuth true",
        "bootstrap_private_azd_environment.sh",
        "validate_private_runner_environment.sh",
        "make foundry-evidence",
        f"git clean -ffdx -e {PRIVATE_PREFIX}/infra/foundry-hosted/.azure/",
    ):
        require(evidence, value, EVIDENCE_WORKFLOW)
    require(evidence, "secrets.POSTGRES_ADMIN_PASSWORD", EVIDENCE_WORKFLOW)
    if evidence.count("secrets.") != 1:
        raise AssertionError(
            f"{EVIDENCE_WORKFLOW} may reference only the PostgreSQL admin password secret."
        )
    for forbidden_operation in (
        "azd provision",
        "azd deploy",
        "make foundry-app-only-release",
        "make foundry-hosted-app-deploy",
        "make foundry-project-connections",
        "make foundry-postgres-lockdown",
    ):
        forbid(evidence, forbidden_operation, EVIDENCE_WORKFLOW)

    observability = (WORKFLOWS / OBSERVABILITY_WORKFLOW).read_text()
    for value in (
        "self-hosted",
        'runs-on: [self-hosted, "${{ vars.PRIVATE_RUNNER_LABEL }}"]',
        PROFILE_MIRROR_SCRIPT,
        "id-token: write",
        "uses: azure/login@v2",
        "bootstrap_private_azd_environment.sh",
        "validate_private_runner_environment.sh",
        "diagnose_hosted_observability.sh",
    ):
        require(observability, value, OBSERVABILITY_WORKFLOW)

    makefile = (Path(PRIVATE_PREFIX) / "Makefile").read_text()
    app_only_preflight_body = makefile.split(
        "foundry-app-only-preflight:\n", maxsplit=1
    )[1].split("\n\nfoundry-hosted-app-deploy:", maxsplit=1)[0]
    require(
        app_only_preflight_body,
        "./scripts/foundry/validate_private_app_release.sh",
        "foundry-app-only-preflight Make target",
    )
    app_only_release_body = makefile.split(
        "foundry-app-only-release:\n", maxsplit=1
    )[1].split("\n\nfoundry-connectivity-proof:", maxsplit=1)[0]
    require_order(
        app_only_release_body,
        (
            "$(MAKE) foundry-app-only-preflight",
            "$(MAKE) foundry-app-deploy",
            "$(MAKE) foundry-app-images-verify",
            "$(MAKE) foundry-hosted-app-deploy",
        ),
        "foundry-app-only-release Make target",
    )
    for forbidden_target in (
        "foundry-provision",
        "foundry-project-connections",
        "foundry-deploy",
        "foundry-connectivity-proof",
        "foundry-postgres-lockdown",
        "foundry-evidence",
    ):
        forbid(
            app_only_release_body,
            forbidden_target,
            "foundry-app-only-release Make target",
        )
    hosted_app_deploy_body = makefile.split(
        "foundry-hosted-app-deploy:", maxsplit=1
    )[1].split("\n\nfoundry-app-only-release:", maxsplit=1)[0]
    require(
        hosted_app_deploy_body,
        "./scripts/foundry/sync_hosted_source.sh",
        "foundry-hosted-app-deploy Make target",
    )
    require(
        hosted_app_deploy_body,
        "./scripts/foundry/deploy_hosted_container.sh",
        "foundry-hosted-app-deploy Make target",
    )
    for forbidden_operation in (
        "ensure_foundry_azd_defaults.sh",
        "foundry-package",
        "azd provision",
        "azd deploy",
    ):
        forbid(
            hosted_app_deploy_body,
            forbidden_operation,
            "foundry-hosted-app-deploy Make target",
        )
    app_image_verify_body = makefile.split(
        "foundry-app-images-verify:\n", maxsplit=1
    )[1].split("\n\nfoundry-app-only-preflight:", maxsplit=1)[0]
    require(
        app_image_verify_body,
        "./scripts/foundry/verify_private_app_images.sh",
        "foundry-app-images-verify Make target",
    )

    app_release_validation = (
        Path(PRIVATE_PREFIX) / "scripts/foundry/validate_private_app_release.sh"
    ).read_text()
    for value in (
        "az cognitiveservices account show",
        "az cognitiveservices account deployment show",
        "az rest",
        "az containerapp env show",
        "az containerapp show",
        "az containerapp registry list",
        "az acr show",
        "az identity show",
        "az role assignment list",
        "az network private-endpoint show",
        "require_project_connection",
        "require_application_insights_connection",
        "require_project_acr_roles",
        "require_container_apps_acr_pull",
        "2025-04-01-preview",
        "foundry_project_resource_name",
        "no secrets or Azure resources were modified",
    ):
        require(
            text=app_release_validation,
            value=value,
            workflow="private app-release validation",
        )
    for forbidden_operation in (
        "RUNTIME_DATABASE_URL",
        "DATABASE_URL",
        "POSTGRES_ADMIN_PASSWORD",
        "azd env set",
        "azd provision",
        "azd deploy",
    ):
        forbid(
            app_release_validation,
            forbidden_operation,
            "private app-release validation",
        )

    app_image_validation = (
        Path(PRIVATE_PREFIX) / "scripts/foundry/verify_private_app_images.sh"
    ).read_text()
    for value in (
        "latestReadyRevisionName",
        "az containerapp revision show",
        "selected private ACR",
    ):
        require(
            text=app_image_validation,
            value=value,
            workflow="private app image validation",
        )

    hosted_container_deploy = (
        Path(PRIVATE_PREFIX) / "scripts/foundry/deploy_hosted_container.sh"
    ).read_text()
    require(
        hosted_container_deploy,
        "az acr repository show",
        "private hosted-agent image verification",
    )

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
        ': "${RUNNER_LABEL:?RUNNER_LABEL is required}"',
        "register_vm_runner.sh",
    )
    main_bicep = (
        Path(PRIVATE_PREFIX) / "infra/foundry-hosted/iac/main.bicep"
    ).read_text()
    require(
        main_bicep,
        "param restoreFoundryAccount bool",
        "private Foundry Bicep",
    )
    forbid(
        main_bicep,
        "param restoreFoundryAccount bool =",
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

    github_actions_identity = (
        Path(PRIVATE_PREFIX) / "infra/github-actions-identity/main.bicep"
    ).read_text()
    require(
        github_actions_identity,
        "param githubSubject string",
        "private GitHub Actions identity",
    )
    forbid(
        github_actions_identity,
        "param githubSubject string =",
        "private GitHub Actions identity",
    )

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
        'set_if_missing RESTORE_FOUNDRY_ACCOUNT "$RESTORE_FOUNDRY_ACCOUNT"',
        "private AZD defaults",
    )
    forbid(
        azd_defaults,
        "restore_foundry_account_default=",
        "private AZD defaults",
    )
    require(
        azd_defaults,
        'cleared RESTORE_FOUNDRY_ACCOUNT because $foundry_account_name is active',
        "private AZD defaults",
    )
    require(
        azd_defaults,
        "azd env set FOUNDRY_TRACE_EVALUATION_RECORD_CONTENT true",
        "private AZD defaults",
    )
    require(
        access_path_body,
        "../../scripts/foundry/ensure_foundry_azd_defaults.sh",
        "foundry-access-path Make target",
    )
    hosted_e2e = (
        Path(PRIVATE_PREFIX) / "scripts/github/foundry_hosted_e2e.sh"
    ).read_text()
    require(
        hosted_e2e,
        "structured_inputs: {trace_evaluation_record_content: true}",
        "private hosted E2E",
    )
    require(
        hosted_e2e,
        '--client-header "$TRACE_EVALUATION_HEADER"',
        "private hosted E2E",
    )
    forbid(
        hosted_e2e,
        "metadata: {trace_evaluation_record_content: true}",
        "private hosted E2E",
    )
    telemetry_verification = (
        Path(PRIVATE_PREFIX) / "backend/evals/verify_telemetry.py"
    ).read_text()
    for value in (
        "FOUNDRY_EVALUATION_AGENT_ID",
        "APPLICATION_INSIGHTS_RESOURCE_ID",
        "evaluation_trace_conversation_count",
        "evaluation_trace_ids",
        "arg_max(timestamp, operation_Id)",
        "extend conversationId = tostring(conversationId)",
        "project operation_Id = tostring(operation_Id)",
        "LogsQueryClient",
        "APP_INSIGHTS_QUERY_MAX_ATTEMPTS",
        "gen_ai.conversation.id",
        "gen_ai.agent.id",
        "gen_ai.input.messages",
        "gen_ai.output.messages",
    ):
        require(telemetry_verification, value, "private telemetry verification")
    eval_runner = (
        Path(PRIVATE_PREFIX) / "backend/evals/foundry_eval_runner.py"
    ).read_text()
    for value in (
        '"type": "azure_ai_traces"',
        '"trace_ids": trace_ids',
        '"query": "{{item.query}}"',
        '"response": "{{item.response}}"',
        "data_source=_build_exact_trace_data_source(trace_ids)",
    ):
        require(eval_runner, value, "private trace evaluation runner")
    evidence_collection = (
        Path(PRIVATE_PREFIX) / "scripts/foundry/collect_private_release_evidence.sh"
    ).read_text()
    for value in (
        "AGENT_ORDER_RESOLUTION_HOSTED_NAME",
        "AGENT_ORDER_RESOLUTION_HOSTED_VERSION",
        'APPLICATION_INSIGHTS_RESOURCE_ID="$application_insights_target"',
        'FOUNDRY_EVALUATION_AGENT_ID="${hosted_agent_name}:${hosted_agent_version}"',
    ):
        require(evidence_collection, value, "private release evidence collection")
    hosted_agent = (Path(PRIVATE_PREFIX) / "backend/foundry/main.py").read_text()
    for value in (
        '"gen_ai.input.messages"',
        '"gen_ai.output.messages"',
        '"parts": [',
        '"type": "text"',
    ):
        require(hosted_agent, value, "private hosted trace messages")
    evidence_target = makefile.split("foundry-evidence:", maxsplit=1)[1].split(
        "\n\nfoundry-release:", maxsplit=1
    )[0]
    require(evidence_target, "ensure-backend-env", "private evidence Make target")

    core_provision_body = makefile.split("foundry-provision:", maxsplit=1)[1].split(
        "\n\nfoundry-project-connections:", maxsplit=1
    )[0]
    require(
        core_provision_body,
        "provision_private_infrastructure.sh",
        "foundry-provision Make target",
    )
    private_profile = Path(
        "agents/order-resolution/deployment/profiles/foundry-private.env"
    ).read_text()
    require(
        private_profile,
        "MANAGE_PROJECT_CONNECTIONS=false",
        "private deployment profile",
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
    require(provision, "preview_only:", provision_name)
    require(provision, "make foundry-provision-preview", provision_name)
    require(
        provision,
        "if: ${{ inputs.preview_only != true }}",
        provision_name,
    )

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
