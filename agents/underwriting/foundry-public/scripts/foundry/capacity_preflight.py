#!/usr/bin/env python3
"""Read-only incremental capacity preflight for the public release lane."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import dataclass
from typing import Any, Protocol


class PreflightError(RuntimeError):
    pass


class AzureClient(Protocol):
    def json(self, *args: str) -> Any: ...


class AzureCli:
    def json(self, *args: str) -> Any:
        command = ["az", *args, "--only-show-errors", "--output", "json"]
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        if result.returncode != 0:
            operation = " ".join(args[:3])
            raise PreflightError(
                f"Azure CLI read failed for {operation}; target identifiers were not displayed."
            )
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise PreflightError(
                f"Azure CLI returned invalid JSON for {' '.join(args[:3])}"
            ) from exc


@dataclass(frozen=True)
class ModelConfig:
    label: str
    deployment_name: str
    model_format: str
    model_name: str
    model_version: str
    sku_name: str
    capacity: int
    capability: str


@dataclass(frozen=True)
class Config:
    mode: str
    subscription_id: str
    resource_group: str
    target_region: str
    foundry_region: str
    foundry_account: str
    foundry_project: str
    postgres_name: str
    postgres_region: str
    postgres_sku: str
    postgres_tier: str
    postgres_version: str
    container_environment: str
    backend_app: str
    frontend_app: str
    registry_name: str
    registry_sku: str
    application_insights_name: str
    log_analytics_name: str
    bot_name: str
    bot_sku: str
    models: tuple[ModelConfig, ...]


REQUIRED_PROVIDERS = (
    "Microsoft.App",
    "Microsoft.BotService",
    "Microsoft.CognitiveServices",
    "Microsoft.ContainerRegistry",
    "Microsoft.DBforPostgreSQL",
    "Microsoft.Insights",
    "Microsoft.ManagedIdentity",
    "Microsoft.OperationalInsights",
    "Microsoft.Quota",
    "Microsoft.Storage",
)

NORTH_AMERICA_REGIONS = frozenset(
    {
        "canadacentral",
        "canadaeast",
        "centralus",
        "eastus",
        "eastus2",
        "mexicocentral",
        "northcentralus",
        "southcentralus",
        "westcentralus",
        "westus",
        "westus2",
        "westus3",
    }
)


def _normalized(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _state(item: dict[str, Any]) -> str:
    properties = item.get("properties")
    return str(
        item.get("provisioningState")
        or item.get("status")
        or item.get("state")
        or (properties.get("provisioningState") if isinstance(properties, dict) else "")
        or ""
    ).casefold()


def _name_value(item: dict[str, Any]) -> str:
    name = item.get("name", "")
    if isinstance(name, dict):
        return str(name.get("value") or name.get("localizedValue") or "")
    return str(name)


def _number(value: Any, description: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise PreflightError(f"{description} did not return a numeric value") from exc


def _walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _postgres_sku_available(payload: Any, sku_name: str, tier_name: str) -> bool:
    expected_sku = sku_name.casefold()
    expected_tier = tier_name.casefold()
    for item in _walk_dicts(payload):
        if (
            str(item.get("name", "")).casefold() == expected_sku
            and str(item.get("tier", item.get("edition", ""))).casefold()
            == expected_tier
        ):
            return True

        editions = item.get("supportedServerEditions")
        if not isinstance(editions, list):
            continue
        for edition in editions:
            if not isinstance(edition, dict):
                continue
            if str(edition.get("name", "")).casefold() != expected_tier:
                continue
            skus = edition.get("supportedServerSkus")
            if isinstance(skus, list) and any(
                isinstance(sku, dict)
                and str(sku.get("name", "")).casefold() == expected_sku
                for sku in skus
            ):
                return True
    return False


class CapacityPreflight:
    def __init__(self, client: AzureClient, config: Config) -> None:
        if config.mode not in {"app_only", "full_infra"}:
            raise PreflightError("Preflight mode must be app_only or full_infra")
        self.client = client
        self.config = config
        self._providers: dict[str, dict[str, Any]] = {}
        self.incremental: dict[str, float] = {
            "foundry_accounts": 0,
            "model_capacity": 0,
            "postgres_servers": 0,
            "container_apps_environments": 0,
            "container_apps": 0,
            "container_registries": 0,
            "application_insights": 0,
            "log_analytics_workspaces": 0,
            "bot_services": 0,
            "teams_channels": 0,
        }
        self.messages: list[str] = []

    def run(self) -> dict[str, Any]:
        configured_regions = {
            _normalized(self.config.target_region),
            _normalized(self.config.foundry_region),
            _normalized(self.config.postgres_region),
        }
        if len(configured_regions) != 1 or not configured_regions <= NORTH_AMERICA_REGIONS:
            raise PreflightError(
                "public capacity preflight requires one North America region"
            )
        self._check_provider_registration()
        self._check_regional_resource_types()
        self._check_foundry_and_models()
        self._check_postgres()
        self._check_container_apps()
        self._check_registry()
        self._check_monitoring()
        if self.config.mode == "full_infra":
            self._check_bot_and_teams()
        if self.config.mode == "app_only" and any(self.incremental.values()):
            raise PreflightError(
                "app_only preflight found infrastructure growth; use the explicit "
                "full-infra preview and reviewed apply authority"
            )
        return {
            "mode": self.config.mode,
            "status": "passed",
            "mutation_performed": False,
            "incremental": self.incremental,
            "messages": self.messages,
        }

    def _provider(self, namespace: str) -> dict[str, Any]:
        if namespace not in self._providers:
            value = self.client.json(
                "provider",
                "show",
                "--namespace",
                namespace,
                "--subscription",
                self.config.subscription_id,
            )
            if not isinstance(value, dict):
                raise PreflightError(f"provider metadata for {namespace} was invalid")
            self._providers[namespace] = value
        return self._providers[namespace]

    def _check_provider_registration(self) -> None:
        missing = [
            namespace
            for namespace in REQUIRED_PROVIDERS
            if str(self._provider(namespace).get("registrationState", "")).casefold()
            != "registered"
        ]
        if missing:
            raise PreflightError(
                "required Azure providers are not registered: " + ", ".join(missing)
            )

    def _check_resource_type_location(
        self, namespace: str, resource_type: str, region: str
    ) -> None:
        resource_types = self._provider(namespace).get("resourceTypes")
        if not isinstance(resource_types, list):
            raise PreflightError(f"{namespace} did not return resource-type location metadata")
        match = next(
            (
                item
                for item in resource_types
                if str(item.get("resourceType", "")).casefold() == resource_type.casefold()
            ),
            None,
        )
        locations = match.get("locations") if isinstance(match, dict) else None
        if not isinstance(locations, list) or _normalized(region) not in {
            _normalized(str(item)) for item in locations
        }:
            raise PreflightError(
                f"{namespace}/{resource_type} is not available in the configured region"
            )

    def _check_regional_resource_types(self) -> None:
        for namespace, resource_type, region in (
            ("Microsoft.App", "managedEnvironments", self.config.target_region),
            ("Microsoft.App", "containerApps", self.config.target_region),
            (
                "Microsoft.CognitiveServices",
                "accounts",
                self.config.foundry_region,
            ),
            (
                "Microsoft.ContainerRegistry",
                "registries",
                self.config.target_region,
            ),
            (
                "Microsoft.DBforPostgreSQL",
                "flexibleServers",
                self.config.postgres_region,
            ),
            ("Microsoft.Insights", "components", self.config.target_region),
            (
                "Microsoft.ManagedIdentity",
                "userAssignedIdentities",
                self.config.target_region,
            ),
            (
                "Microsoft.OperationalInsights",
                "workspaces",
                self.config.target_region,
            ),
            ("Microsoft.Storage", "storageAccounts", self.config.target_region),
        ):
            self._check_resource_type_location(namespace, resource_type, region)

    def _require_available(self, usage: dict[str, Any], required: float, description: str) -> None:
        limit = _number(usage.get("limit"), f"{description} limit")
        current = _number(usage.get("currentValue"), f"{description} current usage")
        if limit - current < required:
            raise PreflightError(
                f"{description} has {max(limit - current, 0):g} available; "
                f"{required:g} incremental capacity is required"
            )

    def _model_catalog(
        self,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        models = self.client.json(
            "cognitiveservices",
            "model",
            "list",
            "--location",
            self.config.foundry_region,
            "--subscription",
            self.config.subscription_id,
        )
        usage = self.client.json(
            "cognitiveservices",
            "usage",
            "list",
            "--location",
            self.config.foundry_region,
            "--subscription",
            self.config.subscription_id,
        )
        if not isinstance(models, list) or not isinstance(usage, list):
            raise PreflightError("Foundry model catalog or quota metadata was invalid")
        return models, usage

    def _check_foundry_and_models(self) -> None:
        accounts = self.client.json(
            "cognitiveservices",
            "account",
            "list",
            "--subscription",
            self.config.subscription_id,
            "--resource-group",
            self.config.resource_group,
        )
        if not isinstance(accounts, list):
            raise PreflightError("Foundry account inventory was invalid")
        account = next(
            (
                item
                for item in accounts
                if isinstance(item, dict)
                and str(item.get("name", "")).casefold() == self.config.foundry_account.casefold()
                and str(item.get("kind", "")).casefold() == "aiservices"
                and _normalized(str(item.get("location", "")))
                == _normalized(self.config.foundry_region)
                and _state(item) == "succeeded"
            ),
            None,
        )
        if account is None:
            self._growth_or_fail("foundry_accounts", "Foundry account", 1)

        projects = self.client.json(
            "cognitiveservices",
            "account",
            "project",
            "list",
            "--subscription",
            self.config.subscription_id,
            "--resource-group",
            self.config.resource_group,
            "--name",
            self.config.foundry_account,
        )
        if not isinstance(projects, list):
            raise PreflightError("Foundry project inventory was invalid")
        project_name = f"{self.config.foundry_account}/{self.config.foundry_project}".casefold()
        project_exists = any(
            isinstance(item, dict)
            and str(item.get("name", "")).casefold()
            in {
                project_name,
                self.config.foundry_project.casefold(),
            }
            and _state(item) in {"", "succeeded"}
            for item in projects
        )
        if not project_exists:
            self._growth_or_fail("foundry_accounts", "Foundry project", 0)

        deployments: list[dict[str, Any]] = []
        if account is not None:
            raw_deployments = self.client.json(
                "cognitiveservices",
                "account",
                "deployment",
                "list",
                "--subscription",
                self.config.subscription_id,
                "--resource-group",
                self.config.resource_group,
                "--name",
                self.config.foundry_account,
            )
            if not isinstance(raw_deployments, list):
                raise PreflightError("Foundry deployment inventory was invalid")
            deployments = raw_deployments

        increments: dict[str, int] = {}
        mismatches: list[str] = []
        for configured in self.config.models:
            exact = next(
                (
                    item
                    for item in deployments
                    if self._deployment_identity_matches(item, configured)
                ),
                None,
            )
            if exact is None:
                increments[configured.label] = configured.capacity
                mismatches.append(configured.label)
                continue
            live_capacity = int((exact.get("sku") or {}).get("capacity", 0))
            if _state(exact) != "succeeded":
                mismatches.append(configured.label)
                increments[configured.label] = configured.capacity
            elif live_capacity == configured.capacity:
                increments[configured.label] = 0
            elif live_capacity < configured.capacity:
                mismatches.append(configured.label)
                increments[configured.label] = configured.capacity - live_capacity
            else:
                mismatches.append(configured.label)
                increments[configured.label] = 0

        if self.config.mode == "app_only" and mismatches:
            raise PreflightError(
                "app_only requires exact healthy Foundry deployments: "
                + ", ".join(sorted(mismatches))
            )

        account_increment = 1 if account is None else 0
        total_increment = sum(increments.values())
        self.incremental["model_capacity"] = total_increment
        if account_increment == 0 and total_increment == 0:
            self.messages.append(
                "Existing healthy Foundry account, project, and model deployments "
                "need zero additional quota."
            )
            return

        models, usage = self._model_catalog()
        if account_increment:
            account_usage = next(
                (
                    item
                    for item in usage
                    if _name_value(item).casefold() == "openai.s0.accountcount"
                ),
                None,
            )
            if not account_usage:
                raise PreflightError("Foundry account quota metadata was not returned")
            self._require_available(account_usage, 1, "Foundry S0 account quota")

        for configured in self.config.models:
            incremental = increments[configured.label]
            self._validate_model(configured, models, usage, incremental)

    @staticmethod
    def _deployment_identity_matches(deployment: dict[str, Any], configured: ModelConfig) -> bool:
        model = (deployment.get("properties") or {}).get("model") or {}
        sku = deployment.get("sku") or {}
        return (
            str(deployment.get("name", "")).casefold() == configured.deployment_name.casefold()
            and str(model.get("format", "")).casefold() == configured.model_format.casefold()
            and str(model.get("name", "")).casefold() == configured.model_name.casefold()
            and str(model.get("version", "")).casefold() == configured.model_version.casefold()
            and str(sku.get("name", "")).casefold() == configured.sku_name.casefold()
        )

    def _validate_model(
        self,
        configured: ModelConfig,
        models: list[dict[str, Any]],
        usage: list[dict[str, Any]],
        incremental: int,
    ) -> None:
        model = next(
            (
                item.get("model", item)
                for item in models
                if isinstance(item, dict)
                and isinstance(item.get("model", item), dict)
                and str(item.get("model", item).get("format", "")).casefold()
                == configured.model_format.casefold()
                and str(item.get("model", item).get("name", "")).casefold()
                == configured.model_name.casefold()
                and str(item.get("model", item).get("version", "")).casefold()
                == configured.model_version.casefold()
            ),
            None,
        )
        if not model:
            raise PreflightError(f"{configured.label} model/version is unavailable")
        capabilities = model.get("capabilities") or {}
        if str(capabilities.get(configured.capability, "")).casefold() != "true":
            raise PreflightError(f"{configured.label} model lacks {configured.capability}")
        sku = next(
            (
                item
                for item in model.get("skus") or []
                if str(item.get("name", "")).casefold() == configured.sku_name.casefold()
            ),
            None,
        )
        if not sku:
            raise PreflightError(f"{configured.label} model does not support the configured SKU")
        if incremental == 0:
            return
        usage_name = str(sku.get("usageName", ""))
        quota = next(
            (item for item in usage if _name_value(item).casefold() == usage_name.casefold()),
            None,
        )
        if not usage_name or not quota:
            raise PreflightError(f"{configured.label} incremental quota metadata was not returned")
        self._require_available(quota, incremental, f"{configured.label} model quota")

    def _check_postgres(self) -> None:
        servers = self.client.json(
            "postgres",
            "flexible-server",
            "list",
            "--subscription",
            self.config.subscription_id,
            "--resource-group",
            self.config.resource_group,
        )
        if not isinstance(servers, list):
            raise PreflightError("PostgreSQL inventory was invalid")
        exact = any(
            isinstance(item, dict)
            and str(item.get("name", "")).casefold() == self.config.postgres_name.casefold()
            and _normalized(str(item.get("location", "")))
            == _normalized(self.config.postgres_region)
            and str((item.get("sku") or {}).get("name", "")).casefold()
            == self.config.postgres_sku.casefold()
            and str((item.get("sku") or {}).get("tier", "")).casefold()
            == self.config.postgres_tier.casefold()
            and str(item.get("version", "")).casefold() == self.config.postgres_version.casefold()
            and _state(item) in {"ready", "succeeded"}
            for item in servers
        )
        if exact:
            self.messages.append(
                "Existing healthy PostgreSQL server needs zero additional capacity."
            )
            return
        self._growth_or_fail("postgres_servers", "PostgreSQL server", 1)
        payload = self.client.json(
            "postgres",
            "flexible-server",
            "list-skus",
            "--location",
            self.config.postgres_region,
            "--subscription",
            self.config.subscription_id,
        )
        sku_exists = _postgres_sku_available(
            payload,
            self.config.postgres_sku,
            self.config.postgres_tier,
        )
        if not sku_exists:
            raise PreflightError("Configured PostgreSQL SKU/tier is unavailable")

    def _check_container_apps(self) -> None:
        environments = self.client.json(
            "containerapp",
            "env",
            "list",
            "--subscription",
            self.config.subscription_id,
            "--resource-group",
            self.config.resource_group,
        )
        apps = self.client.json(
            "containerapp",
            "list",
            "--subscription",
            self.config.subscription_id,
            "--resource-group",
            self.config.resource_group,
        )
        if not isinstance(environments, list) or not isinstance(apps, list):
            raise PreflightError("Container Apps inventory was invalid")
        environment = next(
            (
                item
                for item in environments
                if isinstance(item, dict)
                and str(item.get("name", "")).casefold()
                == self.config.container_environment.casefold()
                and _normalized(str(item.get("location", "")))
                == _normalized(self.config.target_region)
                and _state(item) == "succeeded"
            ),
            None,
        )
        if environment is None:
            self._growth_or_fail("container_apps_environments", "Container Apps environment", 1)
            scope = (
                f"/subscriptions/{self.config.subscription_id}/providers/"
                f"Microsoft.App/locations/{self.config.target_region}"
            )
            quotas = self.client.json("quota", "list", "--scope", scope)
            usages = self.client.json("quota", "usage", "list", "--scope", scope)
            quota = (
                next(
                    (
                        item
                        for item in quotas
                        if _name_value(item).casefold() == "managedenvironmentcount"
                    ),
                    None,
                )
                if isinstance(quotas, list)
                else None
            )
            usage = (
                next(
                    (
                        item
                        for item in usages
                        if _name_value(item).casefold() == "managedenvironmentcount"
                    ),
                    None,
                )
                if isinstance(usages, list)
                else None
            )
            if not quota or not usage:
                raise PreflightError("Container Apps environment quota was not returned")
            limit = (quota.get("properties") or {}).get("limit", {}).get("value")
            usage_properties = usage.get("properties") or {}
            current = usage.get("currentValue")
            if current is None:
                current = usage_properties.get("currentValue")
            if current is None:
                current = (usage_properties.get("usages") or {}).get("value")
            if (
                _number(limit, "Container Apps quota limit")
                - _number(current, "Container Apps quota usage")
                < 1
            ):
                raise PreflightError("Container Apps environment quota has no incremental capacity")

        expected_names = {
            self.config.backend_app.casefold(),
            self.config.frontend_app.casefold(),
        }
        healthy_names = {
            str(item.get("name", "")).casefold()
            for item in apps
            if isinstance(item, dict)
            and _normalized(str(item.get("location", ""))) == _normalized(self.config.target_region)
            and _state(item) == "succeeded"
        }
        missing = expected_names - healthy_names
        if missing:
            self._growth_or_fail("container_apps", "backend/frontend Container Apps", len(missing))
        else:
            self.messages.append(
                "Existing healthy backend and frontend Container Apps need zero "
                "additional infrastructure capacity."
            )

    def _check_registry(self) -> None:
        registries = self.client.json(
            "acr",
            "list",
            "--subscription",
            self.config.subscription_id,
            "--resource-group",
            self.config.resource_group,
        )
        if not isinstance(registries, list):
            raise PreflightError("Container Registry inventory was invalid")
        exact = any(
            isinstance(item, dict)
            and str(item.get("name", "")).casefold() == self.config.registry_name.casefold()
            and _normalized(str(item.get("location", ""))) == _normalized(self.config.target_region)
            and str((item.get("sku") or {}).get("name", "")).casefold()
            == self.config.registry_sku.casefold()
            and _state(item) == "succeeded"
            for item in registries
        )
        if exact:
            self.messages.append(
                "Existing healthy Container Registry needs zero additional capacity."
            )
            return
        self._growth_or_fail("container_registries", "Container Registry", 1)

    def _check_monitoring(self) -> None:
        components = self._resource_group_collection(
            "Microsoft.Insights/components",
            "2020-02-02",
        )
        workspaces = self._resource_group_collection(
            "Microsoft.OperationalInsights/workspaces",
            "2023-09-01",
        )

        application_insights_exists = any(
            isinstance(item, dict)
            and str(item.get("name", "")).casefold()
            == self.config.application_insights_name.casefold()
            and _normalized(str(item.get("location", "")))
            == _normalized(self.config.target_region)
            and _state(item) in {"", "succeeded"}
            for item in components
        )
        workspace_exists = any(
            isinstance(item, dict)
            and str(item.get("name", "")).casefold()
            == self.config.log_analytics_name.casefold()
            and _normalized(str(item.get("location", "")))
            == _normalized(self.config.target_region)
            and _state(item) in {"", "succeeded"}
            for item in workspaces
        )
        if not application_insights_exists:
            self._growth_or_fail(
                "application_insights", "Application Insights component", 1
            )
        if not workspace_exists:
            self._growth_or_fail(
                "log_analytics_workspaces", "Log Analytics workspace", 1
            )
        if application_insights_exists and workspace_exists:
            self.messages.append(
                "Existing healthy Application Insights and Log Analytics resources "
                "need zero additional infrastructure capacity."
            )

    def _check_bot_and_teams(self) -> None:
        resources = self._resource_group_collection(
            "Microsoft.BotService/botServices",
            "2022-09-15",
        )
        bot = next(
            (
                item
                for item in resources
                if isinstance(item, dict)
                and str(item.get("name", "")).casefold() == self.config.bot_name.casefold()
                and str(item.get("kind", "")).casefold() == "azurebot"
                and str((item.get("sku") or {}).get("name", "")).casefold()
                == self.config.bot_sku.casefold()
                and _state(item) in {"", "succeeded"}
            ),
            None,
        )
        if bot is None:
            self._growth_or_fail("bot_services", "Azure Bot Service", 1)
        channels = (
            self._resource_group_collection(
                f"Microsoft.BotService/botServices/{self.config.bot_name}/channels",
                "2022-09-15",
            )
            if bot is not None
            else []
        )
        channel_names = {
            str(item.get("name", "")).casefold() for item in channels if isinstance(item, dict)
        }
        expected_channel = f"{self.config.bot_name}/msteamschannel".casefold()
        channel_exists = expected_channel in channel_names or "msteamschannel" in channel_names
        if not channel_exists:
            self._growth_or_fail("teams_channels", "Microsoft Teams channel", 1)
        if bot is not None and channel_exists:
            self.messages.append(
                "Existing healthy Bot Service and Teams channel need zero "
                "additional infrastructure capacity."
            )

    def _resource_group_collection(
        self,
        resource_path: str,
        api_version: str,
    ) -> list[dict[str, Any]]:
        url = (
            "https://management.azure.com/subscriptions/"
            f"{self.config.subscription_id}/resourceGroups/{self.config.resource_group}/"
            f"providers/{resource_path}?api-version={api_version}"
        )
        payload = self.client.json(
            "rest",
            "--method",
            "get",
            "--url",
            url,
        )
        items = payload.get("value") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            raise PreflightError(f"{resource_path} inventory was invalid")
        return [item for item in items if isinstance(item, dict)]

    def _growth_or_fail(self, key: str, description: str, amount: int) -> None:
        if self.config.mode == "app_only":
            raise PreflightError(f"app_only requires an unchanged healthy existing {description}")
        self.incremental[key] += amount


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise PreflightError(f"Missing required environment value: {name}")
    return value


def _positive_int(name: str) -> int:
    value = _required(name)
    try:
        parsed = int(value)
    except ValueError as exc:
        raise PreflightError(f"{name} must be a positive integer") from exc
    if parsed <= 0:
        raise PreflightError(f"{name} must be a positive integer")
    return parsed


def config_from_environment(mode: str) -> Config:
    return Config(
        mode=mode,
        subscription_id=_required("AZURE_SUBSCRIPTION_ID"),
        resource_group=_required("AZURE_RESOURCE_GROUP"),
        target_region=_required("AZURE_LOCATION"),
        foundry_region=_required("FOUNDRY_LOCATION"),
        foundry_account=_required("FOUNDRY_ACCOUNT_NAME"),
        foundry_project=_required("FOUNDRY_PROJECT_NAME"),
        postgres_name=_required("POSTGRES_SERVER_NAME"),
        postgres_region=_required("POSTGRES_SERVER_LOCATION"),
        postgres_sku=_required("POSTGRES_SKU_NAME"),
        postgres_tier=_required("POSTGRES_SKU_TIER"),
        postgres_version=_required("POSTGRES_VERSION"),
        container_environment=_required("CONTAINER_APPS_ENVIRONMENT_NAME"),
        backend_app=_required("BACKEND_CONTAINER_APP_NAME"),
        frontend_app=_required("FRONTEND_CONTAINER_APP_NAME"),
        registry_name=_required("CONTAINER_REGISTRY_NAME"),
        registry_sku=_required("CONTAINER_REGISTRY_SKU_NAME"),
        application_insights_name=_required("APPLICATION_INSIGHTS_NAME"),
        log_analytics_name=_required("LOG_ANALYTICS_WORKSPACE_NAME"),
        bot_name=_required("BOT_SERVICE_NAME"),
        bot_sku=_required("BOT_SERVICE_SKU_NAME"),
        models=(
            ModelConfig(
                "chat",
                _required("FOUNDRY_MODEL_DEPLOYMENT_NAME"),
                _required("FOUNDRY_MODEL_FORMAT"),
                _required("FOUNDRY_MODEL_NAME"),
                _required("FOUNDRY_MODEL_VERSION"),
                _required("FOUNDRY_MODEL_SKU_NAME"),
                _positive_int("FOUNDRY_MODEL_CAPACITY"),
                "chatCompletion",
            ),
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("app_only", "full_infra"), required=True)
    parser.add_argument("--output", choices=("json", "text"), default="text")
    args = parser.parse_args()
    try:
        result = CapacityPreflight(AzureCli(), config_from_environment(args.mode)).run()
    except PreflightError as exc:
        print(f"capacity preflight failed: {exc}", file=os.sys.stderr)
        return 1
    if args.output == "json":
        print(json.dumps(result, sort_keys=True))
    else:
        for message in result["messages"]:
            print(message)
        print(f"Public capacity preflight passed without changing Azure; mode={args.mode}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
