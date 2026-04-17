import importlib
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("ALLOW_INSECURE_DEFAULT_SECRETS", "true")


def load_service_module(service_dir: str, module_name: str):
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            del sys.modules[name]

    service_path = str(REPO_ROOT / "services" / service_dir)
    repo_path = str(REPO_ROOT)
    sys.path.insert(0, service_path)
    sys.path.insert(0, repo_path)
    try:
        return importlib.import_module(module_name)
    finally:
        if service_path in sys.path:
            sys.path.remove(service_path)
        if repo_path in sys.path:
            sys.path.remove(repo_path)
