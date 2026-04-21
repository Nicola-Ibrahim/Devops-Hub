# Runbook: Database Failover & Recovery (platform-dev)

This runbook describes the steps to take when the application loses connection to the database or when the database service becomes unresponsive.

## 🚨 Symptom
- Application logs show `ConnectionTimeout` or `OperationalError`.
- `poe dev up` hangs at the database initialization step.
- HTTP 500 errors on all database-dependent endpoints.

## 🔍 Diagnosis
1.  **Check Container Status**:
    ```bash
    docker compose ps
    ```
    Is the `db` or `redis` container in an `unhealthy` or `exited` state?

2.  **Inspect Logs**:
    ```bash
    docker compose logs db
    ```
    Look for "Disk full", "Corruption", or "Authentication failed".

3.  **Validate Connectivity (Local)**:
    Try to connect manually from the host:
    ```bash
    # For Redis
    docker compose exec redis redis-cli ping
    ```

## 🛠 Recovery Procedures

### Scenario A: Transient Network/Docker Issue
The most common fix is a clean restart of the infrastructure.
```bash
poe dev down
poe dev up
```

### Scenario B: Data Corruption / Unusable State
If the database volume itself is corrupted, you may need to wipe and recreate it (Warning: This deletes local data!).
```bash
# Stop services
docker compose down -v

# Restart (this will recreate volumes)
poe dev up
```

### Scenario C: Doppler/Secret Mismatch
If the error is `Authentication Failed`, your local `.env` might be out of sync with Doppler.
```bash
poe bootstrap
```

---

## 📈 Escalation
If the issue persists after a full `down -v` and `bootstrap`, contact the DevOps lead or check the #ops-alerts channel for global infrastructure outages.
