# Order Resolution Agent deployment catalog

The Order Resolution Agent is available as three independent deployment
projects. Select one project and follow its README from that project's root;
do not combine its infrastructure, environment configuration, or release
commands with another variant.

All variants implement the same customer-support workflow: low-risk cases can
complete automatically, while high-risk cases pause for deterministic
human-in-the-loop (HITL) approval.

## Choose a deployment variant

| Variant | Application host | Foundry role | Network posture | Choose it when | Project README |
| --- | --- | --- | --- | --- | --- |
| Foundry public | Foundry Responses agent, with an external frontend Container App and internal FastAPI wrapper | Hosts the shared MAF workflow and provides managed agent services | Public Foundry and PostgreSQL; only the frontend is a browser endpoint | You need the public Foundry-hosted agent lane | [Open](foundry-public/README.md) |
| Foundry private | Foundry Responses agent, with an external frontend Container App and internal FastAPI backend | Hosts the shared MAF workflow and provides managed agent services | Private VNet, private endpoints and DNS; only the frontend has external ingress | You require the private, VNet-integrated Foundry lane | [Open](foundry-private/README.md) |
| Azure app-hosted | FastAPI/MAF backend and React frontend on Container Apps | Model inference and report-only evaluation; it does not host the application | The external frontend uses a same-origin API proxy; PostgreSQL supports durable workflow state | You want FastAPI to remain the sole application host | [Open](azure-hosted/README.md) |

## Selection guide

Choose **Foundry public** for the public hosted-agent deployment. Choose
**Foundry private** when private networking, private endpoints, and the
private-runner release process are required. Choose **Azure app-hosted** when
the application must run entirely in the FastAPI/Container Apps deployment and
Foundry is limited to model capabilities.

The Foundry-hosted variants use the Responses protocol for the hosted agent.
The Azure app-hosted variant intentionally has no Foundry agent, manifest, or
agent-runner hosting surface. It uses the same MAF workflow pattern while
keeping application hosting in FastAPI.

## Deployment documentation

Each imported project owns its own operational instructions and target-specific
details:

- **Public Foundry-hosted:** [project overview](foundry-public/README.md) and
  [deployment package](foundry-public/infra/foundry-hosted/README.md).
- **Private Foundry-hosted:** [project overview](foundry-private/README.md)
  and [private deployment package](foundry-private/infra/foundry-hosted/README.md).
- **Azure app-hosted:** [project overview](azure-hosted/README.md) and
  [Azure app-hosted package](azure-hosted/infra/azure-apphosted/README.md).

Run validation and deployment commands from the selected project root. The
project README is authoritative for its environment, credentials, release
sequence, and hosted validation requirements.
