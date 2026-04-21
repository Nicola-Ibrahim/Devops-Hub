# Runbook: Service Restart & State Recovery

This runbook provides standardized steps for restarting services and clearing transient state/caches.

## 🚨 Symptom
- Service is running but returning stale data.
- Service is "Stuck" (not responding to requests but container is up).
- Changes to Doppler secrets aren't showing up in the running app.

## 🛠 Recovery Procedures

### 1. Graceful Application Restart
Try restarting just the specific service first (e.g., `api`):
```bash
docker compose restart api
```

### 2. Full Environment Refresh
If multiple services are acting up, use the `platform-dev` manager to perform a clean restart:
```bash
# This cleans caches, re-syncs doppler, and boots Docker
poe dev down
poe dev up
```

### 3. Clearing Stale Caches
If the app is showing old data, you may need to flush Redis manually:
```bash
# via tob-dev (this happens automatically on 'up')
poe dev up

# OR manually
docker compose exec redis redis-cli flushall
```

### 4. Updating Secrets In-Place
If you added a new secret to Doppler and need the running app to see it:
1. Run `poe bootstrap` (downloads new `.env`).
2. Run `docker compose up -d api` (Docker will detect the `.env` change and recreate only the `api` container).

---

## 📈 Escalation
Standard restarts solve 90% of local development issues. If the container keeps crashing immediately after restart, check `docker compose logs --tail=100 api` for syntax errors or missing environment variables.
