# Disaster Recovery

## Ledger Backup and Restore

OpenPayNet now includes a Docker-based Postgres backup path for the ledger database.

### Backup Assets

- Compose ops job: `ledger-backup`
- Backup directory: `infra/docker/backups/`
- Container script: `scripts/ledger_backup.sh`
- Windows host wrapper: `scripts/ledger_backup.ps1`
- Restore verification utility: `scripts/verify_restore.py`
- Sample transaction seeder: `scripts/seed_db.py`

### Create a Backup

Windows PowerShell:

```powershell
.\scripts\ledger_backup.ps1 -Action backup
```

This writes a timestamped `.sql` file under `infra/docker/backups/`.

Direct Docker invocation:

```powershell
docker-compose --profile ops -f infra/docker/docker-compose.yml run --rm ledger-backup /scripts/ledger_backup.sh backup /backups/ledger-manual.sql
```

### Restore a Backup

Windows PowerShell:

```powershell
.\scripts\ledger_backup.ps1 -Action restore -BackupFile .\infra\docker\backups\ledger-YYYYMMDDTHHMMSSZ.sql
```

Direct Docker invocation:

```powershell
docker-compose --profile ops -f infra/docker/docker-compose.yml run --rm ledger-backup /scripts/ledger_backup.sh restore /backups/ledger-manual.sql
```

The restore script terminates active sessions connected to `ledger` before recreating the database, so it works against a live local stack.

### Restore Smoke Path

1. Start the local stack.
2. Seed a known transaction:

```powershell
py -3 .\scripts\seed_db.py
```

3. Wait for the transaction to appear in the ledger:

```powershell
py -3 .\scripts\verify_restore.py --txn-id <txn_id>
```

4. Create a backup.
5. Restore from that backup.
6. Verify the same transaction still exists:

```powershell
py -3 .\scripts\verify_restore.py --txn-id <txn_id>
```

### Expected Outcome

- Restore completes without SQL errors.
- `GET /v1/ledger/{txn_id}` returns `200`.
- The restored transaction retains its original `trace_id`, `status`, and `timestamp`.

### Verified Smoke Run

- Seeded transaction: `restore-smoke-4f99c5cd-f962-4526-ab78-e29032ae264b`
- Verified readable before backup
- Backed up with `ledger-smoke.sql`
- Restored from `ledger-smoke.sql`
- Verified readable after restore
