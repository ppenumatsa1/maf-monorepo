# MAF Monorepo

This repository catalogs independent Microsoft Agent Framework (MAF) agent
projects. Each project is imported intact so its deployment documentation,
configuration, and validation instructions remain self-contained.

## Project catalog

Each row is an independently operated project. Choose one deployment lane and
follow the README from that project root; do not combine its infrastructure,
configuration, or release commands with another lane.

| Agent | Deployment | Application host | Network posture | Start here |
| --- | --- | --- | --- | --- |
| Order resolution | Foundry public | Foundry Responses agent with Container Apps web delivery | Public Foundry lane | [Project README](agents/order-resolution/foundry-public/README.md) |
| Order resolution | Foundry private | Foundry Responses and Activity agent with Container Apps web delivery | VNet-integrated Foundry and private data dependencies | [Project README](agents/order-resolution/foundry-private/README.md) |
| Order resolution | Azure app-hosted | FastAPI/MAF backend and React frontend on Container Apps | Foundry is limited to models and evaluation | [Project README](agents/order-resolution/azure-hosted/README.md) |
| Underwriting | Foundry public | Foundry-hosted underwriting workflow | Public Foundry lane | [Project README](agents/underwriting/foundry-public/README.md) |

See the [license](LICENSE) and [disclaimer](DISCLAIMER.md) before using this
repository.
