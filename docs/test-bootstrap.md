# Test Bootstrap

OpenPayNet now uses repo-owned Python entrypoints for local and CI test execution.

## Why

The project had mixed launch paths across:

- `python`
- `py -3`
- direct `pytest`
- shell-specific wrappers

That made test startup brittle across Windows, CI, and local shells.

## Standard Entry Points

Install test dependencies with the active interpreter:

```text
python scripts/bootstrap_test_env.py
```

Run the main regression suites:

```text
python scripts/run_tests.py all
```

Run only integration tests:

```text
python scripts/run_tests.py integration
```

Pass extra pytest args:

```text
python scripts/run_tests.py api --pytest-args -k tokenizes_pan
```

Windows helper:

```text
.\scripts\run_tests.ps1 integration
```

## CI Alignment

GitHub Actions now uses the same bootstrap and test runner scripts so local and CI execution share one path.
