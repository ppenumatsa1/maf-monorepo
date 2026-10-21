#!/usr/bin/env python3
"""Read-only Azure capacity and configuration preflight for private provisioning."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlencode


class PreflightError(RuntimeError):
    pass


class AzureClient(Protocol):
    def json(self, *args: str) -> Any: ...


class AzureCli:
    def json(self, *args: str) -> Any:
        command = ["az", *args, "--only-show-errors", "--output", "json"]
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        if result.returncode != 0:
            operation = " ".join(args[:2])
            raise PreflightError(
                f"Azure CLI read failed for {operation} with exit code "
                f"{result.returncode}; profile values and resource identifiers "
                "were not displayed."
            )
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise PreflightError(
                f"Azure CLI returned invalid JSON for {' '.join(args[:2])}"
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
    subscription_id: str
    resource_group: str
    target_region: str
    foundry_region: str
    search_region: str
    cosmos_region: str
    postgres_region: str
    runner_vm_size: str
    create_runner_vm: bool
    enable_container_apps: bool
    search_sku: str
    postgres_sku: str
    postgres_tier: str
    postgres_version: str
    chat: ModelConfig
    embeddings: ModelConfig


REQUIRED_PROVIDERS = (
    "Microsoft.App",
    "Microsoft.Authorization",
    "Microsoft.BotService",
    "Microsoft.CognitiveServices",
    "Microsoft.Compute",
    "Microsoft.ContainerRegistry",
    "Microsoft.ContainerService",
    "Microsoft.DBforPostgreSQL",
    "Microsoft.DocumentDB",
    "Microsoft.Insights",
    "Microsoft.KeyVault",
    "Microsoft.MachineLearningServices",
    "Microsoft.ManagedIdentity",
    "Microsoft.Network",
    "Microsoft.OperationalInsights",
    "Microsoft.Quota",
    "Microsoft.Search",
    "Microsoft.Storage",
)


def _normalized(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _number(value: Any, description: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise PreflightError(f"{description} did not return a numeric value") from exc


def _name_value(item: dict[str, Any]) -> str:
    name = item.get("name", "")
    if isinstance(name, dict):
        return str(name.get("value", ""))
    return str(name)


def _walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


class CapacityPreflight:
    def __init__(self, client: AzureClient, config: Config) -> None:
        self.client = client
        self.config = config
        self._providers: dict[str, dict[str, Any]] = {}
        self.warnings: list[str] = []

    def run(self) -> None:
        self._check_provider_registration()
        self._check_regional_resource_types()
        self._check_aiservices_sku()
        self._check_search_sku_and_quota()
        self._check_postgres_configuration()
        if self.config.create_runner_vm:
            self._check_runner_sku_and_compute_quota()
        if self.config.enable_container_apps:
            self._check_container_apps_quota()
        self._check_ai_resource_and_models()

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
                raise PreflightError(
                    f"provider metadata for {namespace} was not an object"
                )
            self._providers[namespace] = value
        return self._providers[namespace]

    def _check_provider_registration(self) -> None:
        missing: list[str] = []
        for namespace in REQUIRED_PROVIDERS:
            state = str(self._provider(namespace).get("registrationState", ""))
            if state.casefold() != "registered":
                missing.append(f"{namespace} ({state or 'unknown'})")
        if missing:
            raise PreflightError(
                "required Azure providers are not registered: "
                + ", ".join(missing)
                + ". Register each namespace and wait for registrationState=Registered."
            )

    def _check_resource_type_location(
        self, namespace: str, resource_type: str, region: str
    ) -> None:
        resource_types = self._provider(namespace).get("resourceTypes")
        if not isinstance(resource_types, list):
            raise PreflightError(
                f"{namespace} did not return resource-type location metadata"
            )
        match = next(
            (
                item
                for item in resource_types
                if str(item.get("resourceType", "")).casefold()
                == resource_type.casefold()
            ),
            None,
        )
        if not match:
            raise PreflightError(
                f"{namespace}/{resource_type} was absent from provider metadata"
            )
        locations = match.get("locations")
        if not isinstance(locations, list) or not locations:
            raise PreflightError(
                f"{namespace}/{resource_type} returned no definitive regional support data"
            )
        if _normalized(region) not in {_normalized(str(item)) for item in locations}:
            raise PreflightError(
                f"{namespace}/{resource_type} is not available in explicit region "
                f"{region}; update the deployment profile to a supported region. "
                "No fallback region was selected."
            )

    def _check_regional_resource_types(self) -> None:
        checks = (
            ("Microsoft.App", "managedEnvironments", self.config.target_region),
            ("Microsoft.Compute", "virtualMachines", self.config.target_region),
            (
                "Microsoft.ContainerRegistry",
                "registries",
                self.config.target_region,
            ),
            ("Microsoft.Insights", "components", self.config.target_region),
            (
                "Microsoft.ManagedIdentity",
                "userAssignedIdentities",
                self.config.target_region,
            ),
            ("Microsoft.Network", "virtualNetworks", self.config.target_region),
            (
                "Microsoft.OperationalInsights",
                "workspaces",
                self.config.target_region,
            ),
            ("Microsoft.Storage", "storageAccounts", self.config.target_region),
            (
                "Microsoft.CognitiveServices",
                "accounts",
                self.config.foundry_region,
            ),
            (
                "Microsoft.DocumentDB",
                "databaseAccounts",
                self.config.cosmos_region,
            ),
            ("Microsoft.Search", "searchServices", self.config.search_region),
            (
                "Microsoft.DBforPostgreSQL",
                "flexibleServers",
                self.config.postgres_region,
            ),
        )
        for namespace, resource_type, region in checks:
            self._check_resource_type_location(namespace, resource_type, region)

    def _check_aiservices_sku(self) -> None:
        skus = self.client.json(
            "cognitiveservices",
            "account",
            "list-skus",
            "--kind",
            "AIServices",
            "--location",
            self.config.foundry_region,
            "--subscription",
            self.config.subscription_id,
        )
        if not isinstance(skus, list):
            raise PreflightError("AIServices SKU query returned no definitive result")
        sku = next(
            (item for item in skus if str(item.get("name", "")).casefold() == "s0"),
            None,
        )
        if not sku:
            raise PreflightError(
                f"AIServices S0 is unavailable in {self.config.foundry_region}"
            )
        restrictions = sku.get("restrictions") or []
        if restrictions:
            raise PreflightError(
                f"AIServices S0 is restricted in {self.config.foundry_region}: "
                f"{json.dumps(restrictions, sort_keys=True)}"
            )

    def _rest(self, path: str, parameters: dict[str, str]) -> Any:
        url = f"https://management.azure.com{path}?{urlencode(parameters)}"
        return self.client.json("rest", "--method", "get", "--url", url)

    def _check_search_sku_and_quota(self) -> None:
        services = self.client.json(
            "search",
            "service",
            "list",
            "--subscription",
            self.config.subscription_id,
            "--resource-group",
            self.config.resource_group,
        )
        existing_service = isinstance(services, list) and any(
            _normalized(str(service.get("location", "")))
            == _normalized(self.config.search_region)
            and str(
                (service.get("sku") or {}).get("name", "")
                if isinstance(service.get("sku"), dict)
                else service.get("sku", "")
            ).casefold()
            == self.config.search_sku.casefold()
            and str(
                service.get("status")
                or service.get("provisioningState")
                or (service.get("properties") or {}).get("provisioningState", "")
            ).casefold()
            in {"running", "succeeded"}
            for service in services
            if isinstance(service, dict)
        )
        if existing_service:
            self.warnings.append(
                "An existing healthy AI Search service matches the configured "
                "region and SKU; no incremental Search quota is required."
            )
            return

        payload = self._rest(
            (
                f"/subscriptions/{self.config.subscription_id}/providers/"
                f"Microsoft.Search/locations/{self.config.search_region}/usages"
            ),
            {"api-version": "2025-05-01"},
        )
        usages = payload.get("value") if isinstance(payload, dict) else None
        if not isinstance(usages, list):
            raise PreflightError("AI Search usage API returned no definitive result")
        usage = next(
            (
                item
                for item in usages
                if _name_value(item).casefold() == self.config.search_sku.casefold()
            ),
            None,
        )
        if not usage:
            raise PreflightError(
                f"AI Search SKU {self.config.search_sku} is not offered in "
                f"{self.config.search_region}"
            )
        self._require_available(usage, 1, f"AI Search {self.config.search_sku}")

    def _check_postgres_configuration(self) -> None:
        payload = self.client.json(
            "postgres",
            "flexible-server",
            "list-skus",
            "--location",
            self.config.postgres_region,
            "--subscription",
            self.config.subscription_id,
        )
        editions = [
            item
            for item in _walk_dicts(payload)
            if str(item.get("name", "")).casefold()
            == self.config.postgres_tier.casefold()
            and isinstance(item.get("supportedServerSkus"), list)
        ]
        sku = next(
            (
                candidate
                for edition in editions
                for candidate in edition["supportedServerSkus"]
                if str(candidate.get("name", "")).casefold()
                == self.config.postgres_sku.casefold()
            ),
            None,
        )
        if not sku:
            raise PreflightError(
                f"PostgreSQL SKU {self.config.postgres_tier}/"
                f"{self.config.postgres_sku} is unavailable in "
                f"{self.config.postgres_region}"
            )
        if str(sku.get("status", "")).casefold() == "disabled":
            raise PreflightError(
                f"PostgreSQL SKU {self.config.postgres_sku} is disabled in "
                f"{self.config.postgres_region}: {sku.get('reason') or 'no reason returned'}"
            )
        versions = {
            str(version.get("name", ""))
            for item in _walk_dicts(payload)
            for version in (
                item.get("supportedServerVersions")
                if isinstance(item.get("supportedServerVersions"), list)
                else []
            )
            if isinstance(version, dict)
        }
        if self.config.postgres_version not in versions:
            raise PreflightError(
                f"PostgreSQL version {self.config.postgres_version} was not listed as "
                f"supported in {self.config.postgres_region}"
            )

    def _check_runner_sku_and_compute_quota(self) -> None:
        payload = self._rest(
            (
                f"/subscriptions/{self.config.subscription_id}/providers/"
                "Microsoft.Compute/skus"
            ),
            {
                "api-version": "2021-07-01",
                "$filter": f"location eq '{self.config.target_region}'",
            },
        )
        skus = payload.get("value") if isinstance(payload, dict) else None
        if not isinstance(skus, list):
            raise PreflightError("Compute SKU API returned no definitive result")
        matches = [
            item
            for item in skus
            if str(item.get("name", "")).casefold()
            == self.config.runner_vm_size.casefold()
            and str(item.get("resourceType", "virtualMachines")).casefold()
            == "virtualmachines"
        ]
        if not matches:
            raise PreflightError(
                f"runner VM SKU {self.config.runner_vm_size} is unavailable in "
                f"{self.config.target_region}; choose an explicit supported SKU. "
                "No substitute SKU was selected."
            )
        sku = matches[0]
        restrictions = sku.get("restrictions") or []
        if restrictions:
            raise PreflightError(
                f"runner VM SKU {self.config.runner_vm_size} is restricted in "
                f"{self.config.target_region}: "
                f"{json.dumps(restrictions, sort_keys=True)}"
            )
        virtual_machines = self.client.json(
            "vm",
            "list",
            "--subscription",
            self.config.subscription_id,
            "--resource-group",
            self.config.resource_group,
        )
        if isinstance(virtual_machines, list) and any(
            _normalized(str(vm.get("location", "")))
            == _normalized(self.config.target_region)
            and str(
                (vm.get("hardwareProfile") or {}).get("vmSize", "")
            ).casefold()
            == self.config.runner_vm_size.casefold()
            and str(
                vm.get("provisioningState")
                or (vm.get("properties") or {}).get("provisioningState", "")
            ).casefold()
            == "succeeded"
            for vm in virtual_machines
            if isinstance(vm, dict)
        ):
            self.warnings.append(
                "An existing healthy runner VM matches the configured region and "
                "SKU; no incremental compute quota is required."
            )
            return
        capabilities = {
            str(item.get("name", "")): str(item.get("value", ""))
            for item in sku.get("capabilities") or []
        }
        vcpus = int(_number(capabilities.get("vCPUs"), "runner VM vCPU capability"))
        family = str(sku.get("family", ""))
        if not family:
            raise PreflightError(
                f"runner VM SKU {self.config.runner_vm_size} returned no quota family"
            )
        usages = self.client.json(
            "vm",
            "list-usage",
            "--location",
            self.config.target_region,
            "--subscription",
            self.config.subscription_id,
        )
        if not isinstance(usages, list):
            raise PreflightError("compute usage API returned no definitive result")
        for quota_name, label in (
            (family, f"compute family {family}"),
            ("cores", "total regional vCPUs"),
        ):
            usage = next(
                (
                    item
                    for item in usages
                    if _name_value(item).casefold() == quota_name.casefold()
                ),
                None,
            )
            if not usage:
                raise PreflightError(
                    f"compute quota {quota_name} was not returned for "
                    f"{self.config.target_region}"
                )
            self._require_available(usage, vcpus, label)

    def _check_container_apps_quota(self) -> None:
        environments = self.client.json(
            "containerapp",
            "env",
            "list",
            "--subscription",
            self.config.subscription_id,
            "--resource-group",
            self.config.resource_group,
        )
        if isinstance(environments, list) and any(
            _normalized(str(environment.get("location", "")))
            == _normalized(self.config.target_region)
            and str(
                environment.get("provisioningState")
                or (environment.get("properties") or {}).get(
                    "provisioningState", ""
                )
            ).casefold()
            == "succeeded"
            for environment in environments
            if isinstance(environment, dict)
        ):
            self.warnings.append(
                "An existing healthy Container Apps managed environment matches "
                "the configured region; no incremental environment quota is required."
            )
            return

        scope = (
            f"/subscriptions/{self.config.subscription_id}/providers/"
            f"Microsoft.App/locations/{self.config.target_region}"
        )
        quotas = self.client.json("quota", "list", "--scope", scope)
        usages = self.client.json("quota", "usage", "list", "--scope", scope)
        if not isinstance(quotas, list) or not isinstance(usages, list):
            raise PreflightError(
                "Container Apps quota API returned no definitive result; ensure the "
                "Azure CLI quota extension is installed and Microsoft.Quota is registered"
            )
        quota = next(
            (
                item
                for item in quotas
                if _name_value(item).casefold() == "managedenvironmentcount"
            ),
            None,
        )
        usage = next(
            (
                item
                for item in usages
                if _name_value(item).casefold() == "managedenvironmentcount"
            ),
            None,
        )
        if not quota or not usage:
            raise PreflightError(
                "ManagedEnvironmentCount quota or usage was not returned for "
                f"{self.config.target_region}"
            )
        limit = quota.get("properties", {}).get("limit", {}).get("value")
        current = usage.get("properties", {}).get("usages", {}).get("value")
        self._require_limit(limit, current, 1, "Container Apps managed environments")

    def _check_ai_resource_and_models(self) -> None:
        accounts = self.client.json(
            "cognitiveservices",
            "account",
            "list",
            "--subscription",
            self.config.subscription_id,
            "--resource-group",
            self.config.resource_group,
        )
        account = next(
            (
                item
                for item in accounts
                if isinstance(item, dict)
                and str(item.get("kind", "")).casefold() == "aiservices"
                and _normalized(str(item.get("location", "")))
                == _normalized(self.config.foundry_region)
                and str(
                    item.get("provisioningState")
                    or (item.get("properties") or {}).get("provisioningState", "")
                ).casefold()
                == "succeeded"
            ),
            None,
        ) if isinstance(accounts, list) else None
        if account and self._existing_model_deployments_match(
            str(account.get("name", ""))
        ):
            self.warnings.append(
                "An existing healthy AI Services account and exact model "
                "deployments match the configuration; no incremental account or "
                "model quota is required."
            )
            return

        usage = self.client.json(
            "cognitiveservices",
            "usage",
            "list",
            "--location",
            self.config.foundry_region,
            "--subscription",
            self.config.subscription_id,
        )
        if not isinstance(usage, list):
            raise PreflightError("AI Services usage API returned no definitive result")
        account_usage = next(
            (
                item
                for item in usage
                if _name_value(item).casefold() == "openai.s0.accountcount"
            ),
            None,
        )
        if not account_usage:
            raise PreflightError(
                "AIServices/OpenAI S0 account quota was not returned for "
                f"{self.config.foundry_region}"
            )
        self._require_available(account_usage, 1, "AIServices S0 resources")

        models = self.client.json(
            "cognitiveservices",
            "model",
            "list",
            "--location",
            self.config.foundry_region,
            "--subscription",
            self.config.subscription_id,
        )
        if not isinstance(models, list):
            raise PreflightError("model catalog API returned no definitive result")
        if self.config.chat.deployment_name == self.config.embeddings.deployment_name:
            raise PreflightError(
                "chat and embeddings deployment names must be different"
            )
        self._check_model(self.config.chat, models, usage)
        self._check_model(self.config.embeddings, models, usage)

    def _existing_model_deployments_match(self, account_name: str) -> bool:
        if not account_name:
            return False
        deployments = self.client.json(
            "cognitiveservices",
            "account",
            "deployment",
            "list",
            "--subscription",
            self.config.subscription_id,
            "--resource-group",
            self.config.resource_group,
            "--name",
            account_name,
        )
        if not isinstance(deployments, list):
            return False

        def matches(configured: ModelConfig) -> bool:
            return any(
                isinstance(deployment, dict)
                and str(deployment.get("name", "")).casefold()
                == configured.deployment_name.casefold()
                and str(
                    (deployment.get("properties") or {})
                    .get("model", {})
                    .get("format", "")
                ).casefold()
                == configured.model_format.casefold()
                and str(
                    (deployment.get("properties") or {})
                    .get("model", {})
                    .get("name", "")
                ).casefold()
                == configured.model_name.casefold()
                and str(
                    (deployment.get("properties") or {})
                    .get("model", {})
                    .get("version", "")
                ).casefold()
                == configured.model_version.casefold()
                and str((deployment.get("sku") or {}).get("name", "")).casefold()
                == configured.sku_name.casefold()
                and int((deployment.get("sku") or {}).get("capacity", -1))
                == configured.capacity
                and str(
                    (deployment.get("properties") or {}).get(
                        "provisioningState", ""
                    )
                ).casefold()
                == "succeeded"
                for deployment in deployments
            )

        return matches(self.config.chat) and matches(self.config.embeddings)

    def _check_model(
        self,
        configured: ModelConfig,
        models: list[dict[str, Any]],
        usage: list[dict[str, Any]],
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
            raise PreflightError(
                f"{configured.label} model {configured.model_format}/"
                f"{configured.model_name}/{configured.model_version} is unavailable in "
                f"{self.config.foundry_region}"
            )
        capabilities = model.get("capabilities") or {}
        if str(capabilities.get(configured.capability, "")).casefold() != "true":
            raise PreflightError(
                f"{configured.label} model {configured.model_name}/"
                f"{configured.model_version} does not advertise required capability "
                f"{configured.capability}"
            )
        lifecycle = str(model.get("lifecycleStatus", ""))
        if lifecycle and lifecycle.casefold() != "generallyavailable":
            retirement = (model.get("deprecation") or {}).get("inference")
            self.warnings.append(
                f"{configured.label} model lifecycle is {lifecycle}"
                + (f" with inference retirement {retirement}" if retirement else "")
            )
        sku = next(
            (
                item
                for item in model.get("skus") or []
                if str(item.get("name", "")).casefold()
                == configured.sku_name.casefold()
            ),
            None,
        )
        if not sku:
            raise PreflightError(
                f"{configured.label} model {configured.model_name}/"
                f"{configured.model_version} does not support SKU {configured.sku_name}"
            )
        self._validate_model_capacity_setting(configured, sku)
        usage_name = str(sku.get("usageName", ""))
        quota = next(
            (
                item
                for item in usage
                if _name_value(item).casefold() == usage_name.casefold()
            ),
            None,
        )
        if not usage_name or not quota:
            raise PreflightError(
                f"quota {usage_name or '(missing usageName)'} was not returned for "
                f"{configured.label} model"
            )
        self._require_available(
            quota,
            configured.capacity,
            f"{configured.label} model quota {usage_name}",
        )
        capacity = self._rest(
            (
                f"/subscriptions/{self.config.subscription_id}/providers/"
                f"Microsoft.CognitiveServices/locations/{self.config.foundry_region}/"
                "modelCapacities"
            ),
            {
                "api-version": "2024-10-01",
                "modelFormat": configured.model_format,
                "modelName": configured.model_name,
                "modelVersion": configured.model_version,
            },
        )
        entries = capacity.get("value") if isinstance(capacity, dict) else None
        candidates = [
            item
            for item in entries or []
            if str(item.get("properties", {}).get("skuName", "")).casefold()
            == configured.sku_name.casefold()
            and _normalized(str(item.get("location", self.config.foundry_region)))
            == _normalized(self.config.foundry_region)
        ]
        if not candidates:
            raise PreflightError(
                f"capacity API returned no {configured.sku_name} entry for "
                f"{configured.model_name}/{configured.model_version} in "
                f"{self.config.foundry_region}"
            )
        available = max(
            _number(
                item.get("properties", {}).get("availableCapacity"),
                f"{configured.label} available model capacity",
            )
            for item in candidates
        )
        if available < configured.capacity:
            raise PreflightError(
                f"{configured.label} model regional capacity is {available:g}, below "
                f"configured capacity {configured.capacity} in "
                f"{self.config.foundry_region}"
            )

    def _validate_model_capacity_setting(
        self, configured: ModelConfig, sku: dict[str, Any]
    ) -> None:
        capacity = sku.get("capacity") or {}
        allowed = capacity.get("allowedValues")
        if allowed and configured.capacity not in {int(item) for item in allowed}:
            raise PreflightError(
                f"{configured.label} capacity {configured.capacity} is not one of "
                f"the allowed values {allowed}"
            )
        minimum = capacity.get("minimum")
        maximum = capacity.get("maximum")
        step = capacity.get("step")
        if minimum is not None and configured.capacity < int(minimum):
            raise PreflightError(
                f"{configured.label} capacity {configured.capacity} is below minimum "
                f"{minimum}"
            )
        if maximum is not None and configured.capacity > int(maximum):
            raise PreflightError(
                f"{configured.label} capacity {configured.capacity} exceeds maximum "
                f"{maximum}"
            )
        if step and minimum is not None:
            if (configured.capacity - int(minimum)) % int(step) != 0:
                raise PreflightError(
                    f"{configured.label} capacity {configured.capacity} does not follow "
                    f"minimum {minimum} and step {step}"
                )

    def _require_available(
        self, usage: dict[str, Any], required: float, description: str
    ) -> None:
        self._require_limit(
            usage.get("limit"),
            usage.get("currentValue"),
            required,
            description,
        )

    def _require_limit(
        self,
        limit_value: Any,
        current_value: Any,
        required: float,
        description: str,
    ) -> None:
        limit = _number(limit_value, f"{description} limit")
        current = _number(current_value, f"{description} usage")
        available = limit - current
        if available < required:
            raise PreflightError(
                f"{description} quota has {available:g} available "
                f"(limit {limit:g}, used {current:g}); {required:g} is required"
            )


def _bool(value: str) -> bool:
    if value.casefold() == "true":
        return True
    if value.casefold() == "false":
        return False
    raise argparse.ArgumentTypeError("expected true or false")


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("expected a positive integer")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subscription-id", required=True)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--target-region", required=True)
    parser.add_argument("--foundry-region", required=True)
    parser.add_argument("--search-region", required=True)
    parser.add_argument("--cosmos-region", required=True)
    parser.add_argument("--postgres-region", required=True)
    parser.add_argument("--runner-vm-size", required=True)
    parser.add_argument("--create-runner-vm", type=_bool, required=True)
    parser.add_argument("--enable-container-apps", type=_bool, required=True)
    parser.add_argument("--search-sku", required=True)
    parser.add_argument("--postgres-sku", required=True)
    parser.add_argument("--postgres-tier", required=True)
    parser.add_argument("--postgres-version", required=True)
    for prefix in ("chat", "embeddings"):
        parser.add_argument(f"--{prefix}-deployment-name", required=True)
        parser.add_argument(f"--{prefix}-model-format", required=True)
        parser.add_argument(f"--{prefix}-model-name", required=True)
        parser.add_argument(f"--{prefix}-model-version", required=True)
        parser.add_argument(f"--{prefix}-sku-name", required=True)
        parser.add_argument(
            f"--{prefix}-capacity", type=_positive_int, required=True
        )
    return parser


def main() -> int:
    args = _parser().parse_args()
    config = Config(
        subscription_id=args.subscription_id,
        resource_group=args.resource_group,
        target_region=args.target_region,
        foundry_region=args.foundry_region,
        search_region=args.search_region,
        cosmos_region=args.cosmos_region,
        postgres_region=args.postgres_region,
        runner_vm_size=args.runner_vm_size,
        create_runner_vm=args.create_runner_vm,
        enable_container_apps=args.enable_container_apps,
        search_sku=args.search_sku,
        postgres_sku=args.postgres_sku,
        postgres_tier=args.postgres_tier,
        postgres_version=args.postgres_version,
        chat=ModelConfig(
            "chat",
            args.chat_deployment_name,
            args.chat_model_format,
            args.chat_model_name,
            args.chat_model_version,
            args.chat_sku_name,
            args.chat_capacity,
            "chatCompletion",
        ),
        embeddings=ModelConfig(
            "embeddings",
            args.embeddings_deployment_name,
            args.embeddings_model_format,
            args.embeddings_model_name,
            args.embeddings_model_version,
            args.embeddings_sku_name,
            args.embeddings_capacity,
            "embeddings",
        ),
    )
    preflight = CapacityPreflight(AzureCli(), config)
    try:
        preflight.run()
    except PreflightError as exc:
        print(f"Azure capacity preflight failed: {exc}", file=sys.stderr)
        return 1
    for warning in preflight.warnings:
        print(f"Azure capacity preflight warning: {warning}", file=sys.stderr)
    print(
        "Azure capacity preflight passed for "
        f"{config.target_region} with exact runner SKU {config.runner_vm_size}; "
        "no region or SKU fallback was selected."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
