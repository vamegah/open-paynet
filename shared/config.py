import json
import os
from typing import Any


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_text(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    stripped = value.strip()
    return stripped or default


def env_int(name: str, default: int) -> int:
    raw_value = env_text(name)
    if raw_value is None:
        return default
    return int(raw_value)


def env_float(name: str, default: float) -> float:
    raw_value = env_text(name)
    if raw_value is None:
        return default
    return float(raw_value)


def load_secret(
    name: str,
    *,
    default: str | None = None,
    allow_insecure_flag: str = "ALLOW_INSECURE_DEFAULT_SECRETS",
) -> str:
    file_value = env_text(f"{name}_FILE")
    if file_value:
        return open(file_value, "r", encoding="utf-8").read().strip()

    value = env_text(name)
    if value:
        return value

    if default is not None and env_flag(allow_insecure_flag):
        return default
    raise RuntimeError(f"Missing required secret configuration for {name}")


def load_json_config(name: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
    file_value = env_text(f"{name}_FILE")
    if file_value:
        with open(file_value, "r", encoding="utf-8") as handle:
            return json.load(handle)

    value = env_text(name)
    if value:
        return json.loads(value)

    if default is not None and env_flag("ALLOW_INSECURE_DEFAULT_SECRETS"):
        return default
    return default or {}


def parse_scopes(raw_scopes: str | list[str] | None) -> list[str]:
    if raw_scopes is None:
        return []
    if isinstance(raw_scopes, list):
        return sorted({scope.strip() for scope in raw_scopes if scope and scope.strip()})
    return sorted({scope.strip() for scope in raw_scopes.split() if scope.strip()})


def parse_api_keys(raw_value: str) -> dict[str, dict[str, Any]]:
    pairs: dict[str, dict[str, Any]] = {}
    for item in raw_value.split(","):
        if "=" not in item:
            continue
        merchant_id, api_key = item.split("=", 1)
        pairs[merchant_id.strip()] = {
            "api_key": api_key.strip(),
            "role": "merchant",
            "scopes": ["payments:write", "ledger:read"],
        }
    return pairs
