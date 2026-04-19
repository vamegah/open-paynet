import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RAILWAY_CONFIG_PATH = REPO_ROOT / "railway.json"
RAILWAY_SCHEMA_URL = "https://railway.com/railway.schema.json"

SERVICES = {
    "api-gateway": {
        "dockerfile": "services/api-gateway/Dockerfile",
        "healthcheck_path": "/health",
    },
    "auth-service": {
        "dockerfile": "services/auth-service/Dockerfile",
        "healthcheck_path": "/health",
    },
    "payment-service": {
        "dockerfile": "services/payment-service/Dockerfile",
    },
    "fraud-service": {
        "dockerfile": "services/fraud-service/Dockerfile",
    },
    "ledger-service": {
        "dockerfile": "services/ledger-service/Dockerfile",
        "healthcheck_path": "/health",
    },
    "notification-service": {
        "dockerfile": "services/notification-service/Dockerfile",
        "healthcheck_path": "/health",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deploy OpenPayNet services to Railway from CI.")
    parser.add_argument("--project", default=os.getenv("RAILWAY_PROJECT_ID"), help="Railway project ID.")
    parser.add_argument(
        "--environment",
        default=os.getenv("RAILWAY_ENVIRONMENT_NAME", "production"),
        help="Railway environment name or ID.",
    )
    parser.add_argument(
        "--services",
        nargs="*",
        default=list(SERVICES),
        help="Subset of Railway services to deploy. Defaults to all app services.",
    )
    parser.add_argument("--cli-command", default="railway", help="Railway CLI executable name.")
    return parser.parse_args()


def build_config(service_name: str) -> dict:
    service = SERVICES[service_name]
    deploy_config = {
        "restartPolicyType": "ON_FAILURE",
        "restartPolicyMaxRetries": 10,
    }

    healthcheck_path = service.get("healthcheck_path")
    if healthcheck_path:
        deploy_config["healthcheckPath"] = healthcheck_path
        deploy_config["healthcheckTimeout"] = 300

    return {
        "$schema": RAILWAY_SCHEMA_URL,
        "build": {
            "builder": "DOCKERFILE",
            "dockerfilePath": service["dockerfile"],
        },
        "deploy": deploy_config,
    }


def write_railway_config(config: dict) -> bytes | None:
    original = None
    if RAILWAY_CONFIG_PATH.exists():
        original = RAILWAY_CONFIG_PATH.read_bytes()
    RAILWAY_CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return original


def restore_railway_config(original: bytes | None) -> None:
    if original is None:
        RAILWAY_CONFIG_PATH.unlink(missing_ok=True)
        return
    RAILWAY_CONFIG_PATH.write_bytes(original)


def deploy_service(cli_command: str, project: str, environment: str, service_name: str) -> None:
    if service_name not in SERVICES:
        raise ValueError(f"Unknown Railway service: {service_name}")

    config = build_config(service_name)
    original = write_railway_config(config)
    try:
        print(f"Deploying {service_name} to Railway environment {environment}", flush=True)
        command = [
            cli_command,
            "up",
            "-c",
            "-s",
            service_name,
            "-e",
            environment,
            "-p",
            project,
        ]
        subprocess.run(command, cwd=REPO_ROOT, check=True)
    finally:
        restore_railway_config(original)


def main() -> int:
    args = parse_args()
    if not args.project:
        raise SystemExit("Missing Railway project ID. Set --project or RAILWAY_PROJECT_ID.")

    requested_services = args.services or list(SERVICES)
    for service_name in requested_services:
        deploy_service(args.cli_command, args.project, args.environment, service_name)

    print(
        f"Successfully deployed {len(requested_services)} OpenPayNet service(s) to Railway environment {args.environment}.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
