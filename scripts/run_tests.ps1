$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Suite = if ($args.Length -gt 0) { $args[0] } else { "all" }
$ForwardArgs = @()
if ($args.Length -gt 1) {
    $ForwardArgs = $args[1..($args.Length - 1)]
}

Push-Location $RepoRoot
try {
    & python .\scripts\run_tests.py $Suite --pytest-args @ForwardArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
