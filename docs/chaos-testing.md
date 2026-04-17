# Chaos Testing

OpenPayNet now includes a repeatable local chaos drill runner at `tests/chaos-tests/chaos.py`.

## Drills

- `payment-service-stop`
  Verifies the gateway continues to accept and queue requests while `payment-service` is down, and that processing resumes without a lost ledger write after the service comes back.
- `kafka-outage`
  Verifies the gateway degrades safely during broker loss by returning `503` or `504`, and that successful processing resumes after Kafka is restored.

## Run a Single Drill

```powershell
python .\tests\chaos-tests\chaos.py --drill payment-service-stop
```

```powershell
python .\tests\chaos-tests\chaos.py --drill kafka-outage
```

## Run the Full Chaos Suite

```powershell
python .\tests\chaos-tests\chaos.py --drill all
```

## Preconditions

- Docker Desktop is running
- the local stack is already up from `infra/docker/docker-compose.yml`
- `auth-service`, `api-gateway`, and `ledger-service` are healthy before the drill starts

## Assertions

- no duplicate ledger write is created for the disrupted transaction
- broker outage requests fail closed with `503` or `504`
- payment processing recovers after the failed dependency returns
- recovery traffic reaches a terminal ledger state after the service or broker comes back

## Notes

These drills are intentionally disruptive and are best run manually or in an isolated staging environment. They are not enabled as a default CI gate.
