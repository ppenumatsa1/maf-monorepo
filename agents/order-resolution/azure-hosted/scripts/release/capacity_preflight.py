#!/usr/bin/env python3
"""Read-only regional capacity preflight for the Azure-hosted topology."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Protocol


class PreflightError(RuntimeError):
    pass


class AzureClient(Protocol):
    def json(self, *args: str) -> Any: ...


class AzureCli:
    def json(self, *args: str) -> Any:
        command = ["az", *args, "--only-show-errors", "--output", "json"]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
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
    model_format: str
    model_name: str
    model_version: str
    sku_name: str
    capacity: int
    capability: str


@dataclass(frozen=True)
class Config:
    subscription_id: str
    region: str
    postgres_sku: str
    postgres_tier: str
    models: tuple[ModelConfig, ...]


REQUIRED_RESOURCE_TYPES = (
    ("Microsoft.App", "managedEnvironments"),
    ("Microsoft.App", "containerApps"),
    ("Microsoft.CognitiveServices", "accounts"),
    ("Microsoft.ContainerRegistry", "registries"),
    ("Microsoft.DBforPostgreSQL", "flexibleServers"),
    ("Microsoft.Insights", "components"),
    ("Microsoft.ManagedIdentity", "userAssignedIdentities"),
    ("Microsoft.OperationalInsights", "workspaces"),
)
REQUIRED_PROVIDERS = tuple(
    sorted({namespace for namespace, _ in REQUIRED_RESOURCE_TYPES} | {"Microsoft.Quota"})
)


def _normalized(value: Any) -> str:
    return "".join(character for character in str(value).casefold() if character.isalnum())


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
        if str(item.get("name", "")).casefold() != expected_tier:
            continue
        if any(
            str(sku.get("name", "")).casefold() == expected_sku
            for sku in _walk_dicts(item.get("supportedServerSkus", []))
        ):
            return True
    return False


class CapacityPreflight:
    def __init__(self, client: AzureClient, config: Config) -> None:
        self.client = client
        self.config = config
        self.providers: dict[str, dict[str, Any]] = {}
        self.checks: list[str] = []

    def run(self) -> dict[str, Any]:
        self._check_provider_registration_and_regions()
        self._check_aiservices_sku()
        self._check_models_and_quota()
        self._check_postgres_sku()
        self._check_container_apps_quota()
        return {
            "status": "passed",
            "mutation_performed": False,
            "region": self.config.region,
            "checks": self.checks,
        }

    def _provider(self, namespace: str) -> dict[str, Any]:
        if namespace not in self.providers:
            payload = self.client.json(
                "provider",
                "show",
                "--namespace",
                namespace,
                "--subscription",
                self.config.subscription_id,
            )
            if not isinstance(payload, dict):
                raise PreflightError(f"{namespace} provider metadata was invalid")
            self.providers[namespace] = payload
        return self.providers[namespace]

    def _check_provider_registration_and_regions(self) -> None:
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

        for namespace, resource_type in REQUIRED_RESOURCE_TYPES:
            resource_types = self._provider(namespace).get("resourceTypes")
            if not isinstance(resource_types, list):
                raise PreflightError(f"{namespace} resource-type metadata was invalid")
            match = next(
                (
                    item
                    for item in resource_types
                    if str(item.get("resourceType", "")).casefold()
                    == resource_type.casefold()
                ),
                None,
            )
            locations = match.get("locations") if isinstance(match, dict) else None
            if not isinstance(locations, list) or _normalized(self.config.region) not in {
                _normalized(location) for location in locations
            }:
                raise PreflightError(
                    f"{namespace}/{resource_type} is unavailable in the selected region"
                )
        self.checks.append(
            "Container Apps, Foundry, ACR, PostgreSQL, managed identity, "
            "Application Insights, and Log Analytics regional support passed."
        )

    def _check_aiservices_sku(self) -> None:
        skus = self.client.json(
            "cognitiveservices",
            "account",
            "list-skus",
            "--kind",
            "AIServices",
            "--location",
            self.config.region,
            "--subscription",
            self.config.subscription_id,
        )
        if not isinstance(skus, list):
            raise PreflightError("AIServices SKU metadata was invalid")
        s0 = next(
            (item for item in skus if str(item.get("name", "")).casefold() == "s0"),
            None,
        )
        if not s0 or s0.get("restrictions"):
            raise PreflightError("AIServices S0 is unavailable or restricted")

    def _check_models_and_quota(self) -> None:
        models = self.client.json(
            "cognitiveservices",
            "model",
            "list",
            "--location",
            self.config.region,
            "--subscription",
            self.config.subscription_id,
        )
        usage = self.client.json(
            "cognitiveservices",
            "usage",
            "list",
            "--location",
            self.config.region,
            "--subscription",
            self.config.subscription_id,
        )
        if not isinstance(models, list) or not isinstance(usage, list):
            raise PreflightError("Foundry model catalog or quota metadata was invalid")

        required_by_usage: dict[str, int] = defaultdict(int)
        for configured in self.config.models:
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
                raise PreflightError(
                    f"{configured.label} model lacks {configured.capability}"
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
            usage_name = str((sku or {}).get("usageName", ""))
            if not sku or not usage_name:
                raise PreflightError(
                    f"{configured.label} model does not support the configured SKU"
                )
            required_by_usage[usage_name.casefold()] += configured.capacity

        usage_by_name = {
            _name_value(item).casefold(): item
            for item in usage
            if isinstance(item, dict)
        }
        account_quota = usage_by_name.get("aiservices.s0.accountcount")
        if account_quota is None:
            account_quota = usage_by_name.get("openai.s0.accountcount")
        self._require_usage_available(account_quota, 1, "AIServices account quota")
        for usage_name, required in required_by_usage.items():
            self._require_usage_available(
                usage_by_name.get(usage_name),
                required,
                "aggregate Foundry model quota",
            )
        self.checks.append(
            "Foundry account plus chat, evaluator, and embedding model catalog/quota passed."
        )

    @staticmethod
    def _require_usage_available(
        usage: dict[str, Any] | None, required: float, description: str
    ) -> None:
        if usage is None:
            raise PreflightError(f"{description} metadata was not returned")
        limit = _number(usage.get("limit"), f"{description} limit")
        current = _number(usage.get("currentValue"), f"{description} usage")
        if limit - current < required:
            raise PreflightError(f"{description} is insufficient")

    def _check_postgres_sku(self) -> None:
        skus = self.client.json(
            "postgres",
            "flexible-server",
            "list-skus",
            "--location",
            self.config.region,
            "--subscription",
            self.config.subscription_id,
        )
        if not _postgres_sku_available(
            skus, self.config.postgres_sku, self.config.postgres_tier
        ):
            raise PreflightError("Configured PostgreSQL SKU/tier is unavailable")
        self.checks.append("PostgreSQL Flexible Server SKU support passed.")

    def _check_container_apps_quota(self) -> None:
        scope = (
            f"/subscriptions/{self.config.subscription_id}/providers/"
            f"Microsoft.App/locations/{self.config.region}"
        )
        quotas = self.client.json("quota", "list", "--scope", scope)
        usages = self.client.json("quota", "usage", "list", "--scope", scope)
        if not isinstance(quotas, list) or not isinstance(usages, list):
            raise PreflightError("Container Apps quota metadata was invalid")
        quota_by_name = {
            _name_value(item).casefold(): item
            for item in quotas
            if isinstance(item, dict)
        }
        usage_by_name = {
            _name_value(item).casefold(): item
            for item in usages
            if isinstance(item, dict)
        }
        for quota_name, required in (
            ("ManagedEnvironmentCount", 1),
            ("SandboxCores", 2),
        ):
            quota = quota_by_name.get(quota_name.casefold())
            usage = usage_by_name.get(quota_name.casefold())
            if quota is None or usage is None:
                raise PreflightError(
                    f"Container Apps {quota_name} quota metadata was not returned"
                )
            limit = _number(
                ((quota.get("properties") or {}).get("limit") or {}).get("value"),
                f"{quota_name} limit",
            )
            usage_properties = usage.get("properties") or {}
            current = usage.get("currentValue", usage_properties.get("currentValue"))
            if current is None:
                current = (usage_properties.get("usages") or {}).get("value")
            if limit - _number(current, f"{quota_name} usage") < required:
                raise PreflightError(
                    f"Container Apps {quota_name} capacity is insufficient"
                )
        self.checks.append(
            "Container Apps managed-environment and sandbox-core quota passed."
        )


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise PreflightError(f"Missing required profile value: {name}")
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


def config_from_environment() -> Config:
    return Config(
        subscription_id=_required("AZURE_SUBSCRIPTION_ID"),
        region=_required("AZURE_LOCATION"),
        postgres_sku=_required("POSTGRES_SKU_NAME"),
        postgres_tier=_required("POSTGRES_SKU_TIER"),
        models=(
            ModelConfig(
                "chat",
                _required("FOUNDRY_CHAT_MODEL_FORMAT"),
                _required("FOUNDRY_CHAT_MODEL_NAME"),
                _required("FOUNDRY_CHAT_MODEL_VERSION"),
                _required("FOUNDRY_CHAT_DEPLOYMENT_SKU_NAME"),
                _positive_int("FOUNDRY_CHAT_DEPLOYMENT_CAPACITY"),
                "chatCompletion",
            ),
            ModelConfig(
                "embeddings",
                _required("FOUNDRY_EMBEDDINGS_MODEL_FORMAT"),
                _required("FOUNDRY_EMBEDDINGS_MODEL_NAME"),
                _required("FOUNDRY_EMBEDDINGS_MODEL_VERSION"),
                _required("FOUNDRY_EMBEDDINGS_DEPLOYMENT_SKU_NAME"),
                _positive_int("FOUNDRY_EMBEDDINGS_DEPLOYMENT_CAPACITY"),
                "embeddings",
            ),
            ModelConfig(
                "evaluator",
                _required("FOUNDRY_EVALUATOR_MODEL_FORMAT"),
                _required("FOUNDRY_EVALUATOR_MODEL_NAME"),
                _required("FOUNDRY_EVALUATOR_MODEL_VERSION"),
                _required("FOUNDRY_EVALUATOR_DEPLOYMENT_SKU_NAME"),
                _positive_int("FOUNDRY_EVALUATOR_DEPLOYMENT_CAPACITY"),
                "chatCompletion",
            ),
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", choices=("json", "text"), default="text")
    args = parser.parse_args()
    try:
        result = CapacityPreflight(AzureCli(), config_from_environment()).run()
    except PreflightError as exc:
        print(f"capacity preflight failed: {exc}", file=os.sys.stderr)
        return 1
    if args.output == "json":
        print(json.dumps(result, sort_keys=True))
    else:
        for check in result["checks"]:
            print(check)
        print(
            "Azure-hosted regional capacity preflight passed without changing Azure."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
