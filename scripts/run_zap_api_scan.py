import argparse
import subprocess
import sys
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "staging-artifacts"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an OWASP ZAP API scan against the OpenPayNet gateway.")
    parser.add_argument("--docker-network", required=True, help="Docker network the ZAP container should join.")
    parser.add_argument("--openapi-url", required=True, help="Reachable OpenAPI schema URL from inside that Docker network.")
    parser.add_argument("--api-key", default="demo-key", help="Merchant API key sent as X-API-Key during scanning.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for ZAP report artifacts.")
    parser.add_argument("--image", default="ghcr.io/zaproxy/zaproxy:stable")
    parser.add_argument("--format-prefix", default="zap-api-scan")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    json_name = f"{args.format_prefix}.json"
    html_name = f"{args.format_prefix}.html"
    md_name = f"{args.format_prefix}.md"
    container_output_dir = "/tmp/openpaynet-zap"
    container_name = f"openpaynet-zap-{uuid.uuid4().hex[:12]}"

    replacer = (
        "-config replacer.full_list(0).description=api-key "
        "-config replacer.full_list(0).enabled=true "
        "-config replacer.full_list(0).matchtype=REQ_HEADER "
        "-config replacer.full_list(0).matchstr=X-API-Key "
        f"-config replacer.full_list(0).replacement={args.api_key}"
    )

    command = [
        "docker",
        "run",
        "--name",
        container_name,
        "--network",
        args.docker_network,
        args.image,
        "zap-api-scan.py",
        "-t",
        args.openapi_url,
        "-f",
        "openapi",
        "-J",
        f"{container_output_dir}/{json_name}",
        "-r",
        f"{container_output_dir}/{html_name}",
        "-w",
        f"{container_output_dir}/{md_name}",
        "-z",
        replacer,
        "-I",
    ]

    try:
        completed = subprocess.run(command, cwd=REPO_ROOT)
        for artifact_name in (json_name, html_name, md_name):
            subprocess.run(
                [
                    "docker",
                    "cp",
                    f"{container_name}:{container_output_dir}/{artifact_name}",
                    str(output_dir / artifact_name),
                ],
                cwd=REPO_ROOT,
                check=False,
            )
        return completed.returncode
    finally:
        subprocess.run(["docker", "rm", "-f", container_name], cwd=REPO_ROOT, check=False)


if __name__ == "__main__":
    sys.exit(main())
