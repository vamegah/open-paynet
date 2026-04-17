import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SUITES = {
    "unit": ["tests/unit-tests"],
    "api": ["tests/api-tests"],
    "contract": ["tests/contract-tests"],
    "integration": ["tests/integration-tests"],
    "performance": ["tests/performance-tests"],
    "chaos": ["tests/chaos-tests"],
    "security": ["tests/security-tests"],
    "all": ["tests/unit-tests", "tests/api-tests", "tests/contract-tests", "tests/integration-tests"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run OpenPayNet tests with the active Python interpreter.")
    parser.add_argument(
        "suite",
        nargs="?",
        default="all",
        choices=sorted(SUITES),
        help="Named test suite to run.",
    )
    parser.add_argument(
        "--pytest-args",
        nargs=argparse.REMAINDER,
        default=[],
        help="Extra arguments passed through to pytest. Prefix with --pytest-args.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pytest_targets = SUITES[args.suite]
    command = [sys.executable, "-m", "pytest", *pytest_targets, "-v", *args.pytest_args]
    completed = subprocess.run(command, cwd=REPO_ROOT, check=False)
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
