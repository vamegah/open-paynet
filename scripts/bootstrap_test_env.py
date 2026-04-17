import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REQUIREMENTS = [
    "services/api-gateway/requirements.txt",
    "services/ledger-service/requirements.txt",
    "tests/requirements-test.txt",
]


def run_command(args: list[str]) -> None:
    completed = subprocess.run(args, cwd=REPO_ROOT, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install local and CI test dependencies using the active interpreter.")
    parser.add_argument(
        "--requirements",
        action="append",
        default=[],
        help="Additional requirements file to install, relative to repo root. May be passed multiple times.",
    )
    parser.add_argument(
        "--skip-pip-upgrade",
        action="store_true",
        help="Skip the initial pip upgrade step.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    requirement_files = DEFAULT_REQUIREMENTS + args.requirements

    if not args.skip_pip_upgrade:
        run_command([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])

    for relative_path in requirement_files:
        run_command([sys.executable, "-m", "pip", "install", "-r", relative_path])

    print(
        f"Installed OpenPayNet test dependencies with {sys.executable}",
        flush=True,
    )


if __name__ == "__main__":
    main()
