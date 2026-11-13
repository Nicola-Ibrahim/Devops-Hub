# Local developer scripts

Use `scripts/dev.sh` from any working directory. No Python package or command
framework needs to be installed. Bash handles command routing and Docker Compose;
standalone Python 3 helpers handle private env files and structured data.

| Command | Behavior |
| --- | --- |
| `scripts/dev.sh help` | Commands and valid options; no side effects |
| `scripts/dev.sh up` | Check Docker, preserve/init private env files, build and wait for core readiness |
| `scripts/dev.sh up --resources --application-delivery` | Include explicitly selected workers; configured targets remain required |
| `scripts/dev.sh down` | Stop all platform profiles while preserving volumes |
| `scripts/dev.sh status` | Service status |
| `scripts/dev.sh logs api` | Follow an allowlisted service's logs |
| `scripts/dev.sh clean` | Preview approved cache directories |
| `scripts/dev.sh clean --apply` | Remove only those caches; refuse symlink paths |

Daily startup does not install packages, run Ansible or synchronize dependencies.
Developer-machine installation remains an explicit optional operation under
`ops/local/ansible/`. Backend and frontend dependency/check commands live in their
own READMEs. No compatibility aliases for the old tob/poe developer commands remain.

`scripts/helpers/init_env.py` is an ordinary Python file called by Bash; it is
not an installable package. Component env files are private and persistent.
Cleanup never removes env files, `.local`, databases, Docker volumes, `.venv` or
`node_modules`, and never runs a global prune.

Operational backup/restore and host-storage scripts live in
`ops/hosting/scripts/`; the backend image owns `backend/docker-entrypoint.sh`.
Their Python helpers are separate files. Host-storage initialization can format
a reviewed EBS volume and must never run through the local developer entrypoint.

Run safe script checks without starting containers:

```sh
python3 -m unittest discover -s scripts/tests -v
bash -n scripts/dev.sh ops/hosting/scripts/*.sh
sh -n backend/docker-entrypoint.sh
```

Opt-in packaged-stack acceptance is a backend pytest test, not a developer command:

```sh
cd backend
PLATFORM_RUN_PACKAGED_ACCEPTANCE=1 PLATFORM_TEST_DOCKER_URL=unix:///var/run/docker.sock \
  .venv/bin/pytest -q tests/acceptance/test_packaged_stack.py
```

It requires prebuilt `devops-hub/backend:acceptance` and
`devops-hub/frontend:acceptance` images (or explicit PLATFORM_TEST_API_IMAGE and
PLATFORM_TEST_FRONTEND_IMAGE references), allocates a unique Compose project and
synthetic credentials, uses local ports 8000/3000, and removes only its owned test
resources. It does not read developer env files. Without explicit opt-in it skips.
This command creates disposable resources; it is separate from the safe checks.
