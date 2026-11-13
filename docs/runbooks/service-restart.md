# Local service restart

Inspect the local stack before restarting:

```sh
docker compose --profile app ps
docker compose --profile app restart api
```

A restart does not reload changed component env files. After an intentional local
configuration edit, recreate the affected service with `docker compose --profile
app up -d api`. Do not print resolved Compose configuration or environment values.
Keep database passwords and encryption keys stable while their data is retained.

There is no Redis service or Doppler synchronization in this local stack. Do not
flush unrelated services, prune Docker globally or remove volumes for routine
recovery. See [operations](../operations.md) for readiness, worker profiles and
control-plane backup/restore. Server deployment and rollback are separately scoped.
