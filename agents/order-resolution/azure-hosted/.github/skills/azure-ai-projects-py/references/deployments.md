# Deployments Operations Reference

## Overview

Deployments represent AI model deployments in your Azure AI Foundry project.

## List Deployments

### List All Deployments

```python
deployments = project_client.deployments.list()
for deployment in deployments:
    print(f"Name: {deployment.name}")
    print(f"Model: {deployment.model_name}")
    print(f"Publisher: {deployment.model_publisher}")
    print("---")
```

### Filter by Publisher

```python
# List only OpenAI model deployments
for deployment in project_client.deployments.list(model_publisher="OpenAI"):
    print(f"{deployment.name}: {deployment.model_name}")
```

### Filter by Model Name

```python
# List deployments of a specific model
for deployment in project_client.deployments.list(model_name="gpt-4o"):
    print(f"{deployment.name}: {deployment.model_version}")
```

## Get Deployment

```python
from azure.ai.projects.models import ModelDeployment

deployment = project_client.deployments.get("my-deployment-name")

if isinstance(deployment, ModelDeployment):
    print(f"Type: {deployment.type}")
    print(f"Name: {deployment.name}")
    print(f"Model Name: {deployment.model_name}")
    print(f"Model Version: {deployment.model_version}")
    print(f"Model Publisher: {deployment.model_publisher}")
    print(f"Capabilities: {deployment.capabilities}")
```

## Deployment Properties

```python
deployment = project_client.deployments.get("gpt-4o-mini")

# Available properties
print(f"Name: {deployment.name}")           # Deployment name
print(f"Model: {deployment.model_name}")    # e.g., "gpt-4o-mini"
print(f"Version: {deployment.model_version}")  # e.g., "2024-07-18"
print(f"Publisher: {deployment.model_publisher}")  # e.g., "OpenAI"
print(f"Type: {deployment.type}")           # Deployment type
print(f"Capabilities: {deployment.capabilities}")  # Model capabilities
```

## Using Deployments

### Dynamic Model Selection

```python
# Find available GPT-4 deployments
gpt4_deployments = [
    d for d in project_client.deployments.list()
    if "gpt-4" in d.model_name.lower()
]

if gpt4_deployments:
    deployment_name = gpt4_deployments[0].name
    
    agent = project_client.agents.create_agent(
        model=deployment_name,
        name="dynamic-agent",
        instructions="You are helpful.",
    )
```

### Capability Checking

```python
deployment = project_client.deployments.get("my-deployment")

# Check if deployment supports certain capabilities
if deployment.capabilities:
    supports_vision = deployment.capabilities.get("vision", False)
    supports_functions = deployment.capabilities.get("function_calling", False)
    
    print(f"Vision: {supports_vision}")
    print(f"Function Calling: {supports_functions}")
```

## Environment Variables Pattern

```bash
# Store deployment name in environment
AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-4o-mini
```

```python
import os

# Use deployment from environment
agent = project_client.agents.create_agent(
    model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
    name="my-agent",
    instructions="You are helpful.",
)
```

## List Available Models

```python
# Print all available models grouped by publisher
from collections import defaultdict

deployments_by_publisher = defaultdict(list)

for deployment in project_client.deployments.list():
    deployments_by_publisher[deployment.model_publisher].append(deployment)

for publisher, deployments in deployments_by_publisher.items():
    print(f"\n{publisher}:")
    for d in deployments:
        print(f"  - {d.name} ({d.model_name} v{d.model_version})")
```

## Order Resolution Delivery Status

This is the current release record for the three Order Resolution deployment
lanes after the intentional 2026-07-28 teardown and recovery work. A lane is
only **validated** when its required smoke, E2E, evaluation, and telemetry
gates have current evidence.

| Lane | Status | Current evidence | Pending gate / blocker |
| --- | --- | --- | --- |
| Azure-hosted | **Deployed and validated** | Backend and frontend redeployed from the monorepo; hosted UI passed all 7 Playwright flows; Foundry evaluation passed 2/2; 32 recent workflow/HITL dependency spans were recorded. | None. |
| Foundry-public | **Deployed and validated** | Infrastructure, backend, frontend, and hosted agent are deployed. Version 14 passed Responses smoke; deployed browser E2E passed 7/7; hosted Responses E2E completed low- and high-risk flows; Foundry evaluation passed 2/2; telemetry found 51 correlated rows with no exception rows. | None. |
| Foundry-private | **Prepared; deployment pending** | Recovery IaC, staged project-connection workflow, private-runner enforcement, and release-order validation are implemented and statically validated. | Recover/register the VNet-connected `foundry-private-v2` runner, complete staged provision, prove connectivity before PostgreSQL lockdown, then run hosted E2E, evaluation, and telemetry. |

### Public Foundry: remote source-build failure

**Symptom.** After clean provisioning, the former hosted-agent source-code
path (`dependency_resolution: remote_build`) failed before publishing any agent
image to ACR:

```text
ImageError: Container image not found
```

The failure was reproduced with the unmodified official Microsoft Python
hosted-agent sample through `AIProjectClient.create_version_from_code`. That
ruled out the Order Resolution implementation, generated source folder, and
legacy agent manifest as root causes.

**What was verified.**

1. The Foundry project managed identity needs `Container Registry Repository
   Reader`, and ACR needs `azureADAuthenticationAsArmPolicy` enabled.
2. The current Agent Service also requires `AcrPull` for this project: removing
   it reproduced the explicit service error that the workspace managed identity
   lacked `AcrPull`.
3. An official sample image built in the same ACR activated immediately. The
   unresolved platform boundary is therefore Foundry's remote source-build
   path, not project-to-ACR image access.

**Repository fix.** Public Foundry now deploys a container image rather than
remote source code:

1. `sync_hosted_source.sh` copies canonical backend source into the generated
   hosted-agent build context.
2. `backend/Dockerfile.hosted` starts the adapter as
   `python -m foundry.main`, preserving the `/app` import root and hosted
   `/readiness` behavior.
3. `deploy_hosted_container.sh` builds that context in ACR.
4. `deploy_hosted_container.py` creates and polls the hosted-agent version
   with the non-reserved runtime settings, including the Azure PostgreSQL URL
   and model deployment.
5. The script updates the AZD agent-version metadata, so operational commands
   resolve the active version correctly.

**Live confirmation.** The release created
`order-resolution-hosted` version `14` from the repository-built image and
completed `ORD-1001` in conversation
`conv_ad0825e2b0ac6dc400W59cDlBuRk8Km64lb5pFzMYMaYWzoppD`. The active
agent used `gpt-4o-mini` and the configured Azure PostgreSQL server; its smoke
trace ID is `3ae160e935d56a643fd1d2204c2dcacf`.

**Release-gate confirmation.** The current deployment also passed the seven
deployed browser scenarios and hosted Responses E2E for low-risk,
conversation-continuity, and approved high-risk requests. Foundry trace
evaluation `eval_ba88f785636644758e0027e8be963ed2` /
`evalrun_9f4964e7e8f14ebdbbec85eb549c4112` judged the two fresh E2E
conversations as 2 passed, 0 failed, 0 errored. Application Insights found 51
correlated telemetry rows and no exception rows for those conversations.

For the detailed operational record, see:
`agents/order-resolution/foundry-public/docs/design/issues-changes-fixes.md`.
