from __future__ import annotations

from app.core.config import Settings
from app.infrastructure.llm.foundry_client import FoundryLLMClient


def create_foundry_maf_client(settings: Settings) -> FoundryLLMClient:
    return FoundryLLMClient(settings)
