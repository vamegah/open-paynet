import argparse
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:
    print("PyYAML is required for validate_k8s_manifests.py. Run: python scripts/bootstrap_test_env.py")
    raise SystemExit(1)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_DIR = REPO_ROOT / "infra" / "kubernetes"
EXPECTED_OFFLINE_KUBECTL_ERRORS = (
    "connect: connection refused",
    "no configuration has been provided",
    "current-context is not set",
    "the connection to the server localhost:8080 was refused",
    "dial tcp",
)


def load_documents(manifest_dir: Path) -> list[tuple[Path, dict]]:
    documents: list[tuple[Path, dict]] = []
    for path in sorted(manifest_dir.glob("*.yaml")):
        if path.name in {"kustomization.yaml", "secret.example.yaml"}:
            continue
        for item in yaml.safe_load_all(path.read_text(encoding="utf-8")):
            if item:
                documents.append((path, item))
    return documents


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def validate_manifest_policies(documents: list[tuple[Path, dict]]) -> list[str]:
    errors: list[str] = []
    docs_by_kind: dict[str, list[tuple[Path, dict]]] = {}
    for path, doc in documents:
        docs_by_kind.setdefault(doc.get("kind", ""), []).append((path, doc))

    require("ExternalSecret" in docs_by_kind, "Missing ExternalSecret manifest", errors)
    require("Certificate" in docs_by_kind, "Missing Certificate manifest", errors)
    require("PodDisruptionBudget" in docs_by_kind, "Missing PodDisruptionBudget manifest", errors)

    ingress_docs = docs_by_kind.get("Ingress", [])
    require(bool(ingress_docs), "Missing Ingress manifest", errors)
    for path, ingress in ingress_docs:
        tls_entries = ingress.get("spec", {}).get("tls", [])
        require(bool(tls_entries), f"{path.name} must define TLS hosts", errors)
        annotations = ingress.get("metadata", {}).get("annotations", {})
        require(
            annotations.get("nginx.ingress.kubernetes.io/force-ssl-redirect") == "true",
            f"{path.name} must force SSL redirect",
            errors,
        )

    stateful_targets = {"kafka", "redis", "ledger-db", "elasticsearch"}
    statefulsets = {
        doc.get("metadata", {}).get("name"): doc for _, doc in docs_by_kind.get("StatefulSet", [])
    }
    for name in stateful_targets:
        require(name in statefulsets, f"Missing StatefulSet for {name}", errors)

    kafka = statefulsets.get("kafka")
    if kafka:
        require(kafka.get("spec", {}).get("replicas", 0) >= 3, "Kafka must run with at least 3 replicas", errors)

    elasticsearch = statefulsets.get("elasticsearch")
    if elasticsearch:
        require(
            elasticsearch.get("spec", {}).get("replicas", 0) >= 3,
            "Elasticsearch must run with at least 3 replicas",
            errors,
        )

    deployments = {
        doc.get("metadata", {}).get("name"): doc for _, doc in docs_by_kind.get("Deployment", [])
    }
    for name in {"api-gateway", "auth-service", "payment-service", "fraud-service", "ledger-service", "notification-service", "audit-service"}:
        deployment = deployments.get(name)
        require(deployment is not None, f"Missing Deployment for {name}", errors)
        if deployment is not None:
            require(
                deployment.get("spec", {}).get("replicas", 0) >= 2,
                f"{name} must run with at least 2 replicas",
                errors,
            )

    return errors


def kubectl_available() -> bool:
    completed = subprocess.run(
        ["kubectl", "version", "--client=true"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode == 0


def kubectl_cluster_reachable() -> bool:
    completed = subprocess.run(
        ["kubectl", "cluster-info", "--request-timeout=5s"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        return True

    output = f"{completed.stdout}\n{completed.stderr}".lower()
    if any(fragment in output for fragment in EXPECTED_OFFLINE_KUBECTL_ERRORS):
        print("kubectl cluster not reachable; skipping cluster-backed client dry-run checks")
        return False

    print(output.strip())
    return False


def kubectl_kustomize_check(manifest_dir: Path) -> list[str]:
    kustomization = manifest_dir / "kustomization.yaml"
    if not kustomization.exists():
        return []

    completed = subprocess.run(
        ["kubectl", "kustomize", str(manifest_dir)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout).strip()
        return [f"kustomize render failed: {stderr}"]
    return []


def kubectl_client_check(manifest_dir: Path) -> list[str]:
    if not kubectl_available():
        print("kubectl is not installed; skipping kubectl-based manifest rendering checks")
        return []

    errors = kubectl_kustomize_check(manifest_dir)
    if errors:
        return errors

    if not kubectl_cluster_reachable():
        return []

    errors: list[str] = []
    for path in sorted(manifest_dir.glob("*.yaml")):
        if path.name in {"kustomization.yaml", "secret.example.yaml"}:
            continue
        completed = subprocess.run(
            ["kubectl", "create", "--dry-run=client", "--validate=false", "-f", str(path), "-o", "yaml"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            stderr = (completed.stderr or completed.stdout).strip()
            errors.append(f"{path.name}: kubectl client dry-run failed: {stderr}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline validation for OpenPayNet Kubernetes manifests.")
    parser.add_argument("--manifest-dir", default=str(DEFAULT_MANIFEST_DIR))
    args = parser.parse_args()

    manifest_dir = Path(args.manifest_dir).resolve()
    documents = load_documents(manifest_dir)
    errors = validate_manifest_policies(documents)
    errors.extend(kubectl_client_check(manifest_dir))

    if errors:
        for error in errors:
            print(error)
        return 1

    print("Kubernetes manifests passed offline validation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
