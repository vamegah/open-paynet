$ErrorActionPreference = "Stop"

param(
    [ValidateSet("backup", "restore")]
    [string]$Action = "backup",
    [string]$BackupFile = ""
)

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ComposeWorkdir = Join-Path $RepoRoot "infra\docker"
$BackupDir = Join-Path $ComposeWorkdir "backups"
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

if (-not $BackupFile) {
    $stamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
    $BackupFile = Join-Path $BackupDir "ledger-$stamp.sql"
}

$ComposeFile = "docker-compose.yml"
$ComposeFilePath = Join-Path $ComposeWorkdir $ComposeFile
$RelativeBackupPath = "/backups/" + [IO.Path]::GetFileName($BackupFile)

if ($Action -eq "backup") {
    docker-compose --env-file (Join-Path $ComposeWorkdir ".env") --profile ops -f $ComposeFilePath run --rm ledger-backup /scripts/ledger_backup.sh backup $RelativeBackupPath
    Write-Output "Backup created at $BackupFile"
    exit 0
}

if (-not (Test-Path $BackupFile)) {
    throw "Backup file not found: $BackupFile"
}

docker-compose --env-file (Join-Path $ComposeWorkdir ".env") --profile ops -f $ComposeFilePath run --rm ledger-backup /scripts/ledger_backup.sh restore $RelativeBackupPath
Write-Output "Restore completed from $BackupFile"
