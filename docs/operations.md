# Platform operations

This guide describes the local Docker prototype and the separately documented
release path. The local prototype needs no AWS account or GitHub integration; it
does not make application previews or cloud deployment ready. The API and
resource worker own developer-requested PostgreSQL resources. Both workers are
optional: use `resources` for database provisioning and `application-delivery`
for application delivery.
Publishing an image is not a deployment.

## Local Docker demo

Requirements: Docker Engine/Desktop with Compose v2, Python 3.12/`uv` for local
backend checks, and Node.js 22/npm for dashboard checks. Start Docker before
starting Compose.

```sh
scripts/dev.sh up
```

The startup script creates ignored `backend/.env` and `frontend/.env` files if
they are absent. The backend file holds local PostgreSQL and platform credentials
as well as provider settings; the frontend file holds its server-side API URL.
Existing local secret files are reused when present, so an existing database is
not assigned new credentials. Both env files are private local inputs: never
commit them or print `docker compose config`, `docker inspect` environment, or
their contents. Docker environment values are visible to users with Docker
daemon access. Keep the resource encryption key and installation ID stable while
encrypted control-plane records exist; rotation needs a separate procedure.
The backend env file is shared by the local backend services, including
PostgreSQL. It is not a per-process secret isolation boundary. Preserve it when
stopping containers or retaining the database volume; restore it if lost.

The normal `--profile app` Compose startup starts PostgreSQL 16, an explicit
Alembic migration job, OPA, the FastAPI API and the Next.js dashboard. The
resource worker uses the `resources` profile and the application worker uses
`application-delivery`. Both use the backend image and wait for PostgreSQL health
and successful migration. Resource requests remain queued and leases are not
cleaned up while the resource worker is stopped.
The API is published to host loopback on
8000, the dashboard on 3000, and provisioned developer PostgreSQL endpoints are
advertised on host loopback. PostgreSQL control-plane data uses a named volume.
`docker compose --profile app --profile resources --profile application-delivery down`
stops selected containers and preserves volumes;
never add `-v` or run `docker system prune` as routine cleanup.

Only worker services receive `/var/run/docker.sock`; the API and migration job do
not. Access to that socket is equivalent to host root, so keep this prototype on
a trusted developer machine. The script discovers the socket's group ID for the
workers without making the API privileged. Do not publish the API or Docker
socket to the public network.

The backend image's entrypoint drops to its fixed non-root service UID. Local
Compose injects `backend/.env` into PostgreSQL, migration, API and selected
workers; it injects `frontend/.env` only into the dashboard. `compose.yaml` is
for local development only. CI builds images and runs isolated test dependencies.

The resource worker's `PLATFORM_LOCAL_PROVIDER_ENABLED` setting defaults to
false, so start it only after enabling and verifying the local target. The
application worker receives no approved image list by default, so its
Docker delivery adapter is not configured. The application worker process alone
does not make previews provisionable or ready. Keep these defaults until local
provider and application delivery readiness, digest approval, credential
isolation, host networking, retry/restart and cleanup acceptance checks have
passed.

After those acceptance checks, an operator can approve an image already built in
the local Docker daemon by its immutable image ID. Replace `<local-tag>` with
that image's local tag; this inspects metadata only and does not start a
container:

```sh
docker image inspect --format '{{.Id}}' <local-tag>
```

The result must be exactly `sha256:` followed by 64 hexadecimal characters.
Use the actual digest from `docker image inspect`, not the placeholder below.
Put the approved digest and provider opt-in in the ignored `backend/.env` file.
Then start both optional workers:

```sh
scripts/dev.sh up --resources --application-delivery
```

The approved image must be present in the local daemon; this flow needs no
registry, GitHub integration or cloud credentials. Delivered app
URLs bind to `127.0.0.1` only and are not reachable from other hosts. No payment
provider is included. This prototype validates a local app/database and an
in-process or mock payment path only. When a database is attached, the app and
database use an internal-only Docker bridge network; external payment provider
or sandbox connectivity may therefore be unavailable. External payment provider
connectivity is separate work. Enabling the local provider is an operator action
after acceptance; merely starting the worker never starts an application by
itself.

The default catalog remains non-requestable until that acceptance is complete.
The API's `/health/live` and `/health/ready` endpoints report process and DB/schema
readiness. Readiness depends on the explicitly applied schema revision; API
startup never migrates the shared database.

## Host setup and TLS

Install the pinned Ansible collections once, then syntax-check before applying to
a disposable Ubuntu host:

```sh
cd ops/hosting/ansible
ansible-galaxy collection install -r ../../ansible-requirements.yml
ansible-playbook -i inventory/production.yml playbooks/setup.yml --syntax-check
```

For a remote host, configure its SSH user and port and verify key-based
reconnection first. Pass `-e ssh_key_access_confirmed=true` only after that
verification. The hardening playbook allows that SSH port before enabling UFW,
validates `sshd` configuration and does not restart SSH until validation succeeds.
Do not set SSH ingress to `0.0.0.0/0` in AWS. Ansible installs distro Docker
packages and Compose, validates Nginx before reload, and uses Certbot webroot
issuance plus its renewal timer when `server_name` and `certbot_email` are set.
TLS needs a real DNS name pointing at the host and reachable ports 80/443.

Host-secret delivery requires a separately configured operator process. The unused
Doppler integration is removed; local component env files are not a server secret-delivery contract.

## Immutable release and rollback

`Platform CI` runs backend/PostgreSQL tests, dashboard checks, Ansible/Terraform
static checks and Compose validation. It builds both images without publishing
for pull requests and when AWS publishing is not configured, so local development
does not need AWS credentials. With the optional AWS publisher configured,
`Publish Platform Images` starts only after the exact `main` commit passes the
complete `Platform CI` workflow; that downstream workflow builds each image once,
pushes run-unique tags to immutable ECR, scans the exact pushed digests and records the full
`repository@sha256:...` references. With no publisher role configured, the
optional publish job is skipped. Publishing does not send a deploy command.

The legacy server deployment workflow, Ansible deployment playbook and release
script were removed because they reused the local-only Compose manifest. There
is no active server deployment or automatic rollback path. Future delivery must
first define target configuration, private credentials, migration compatibility,
readiness and rollback. Existing hosting Terraform is retained without resource
address or state changes; it is not a working application deployment.

## Queue monitoring

Prometheus is outside the simplified local Compose stack. The API still exposes
an authenticated `/metrics` endpoint. The sample scrape and alert configuration
in `ops/monitoring/` can be used by an operator-managed Prometheus instance;
it needs a private bearer token file and explicit network access to the API.

The backend exports queue and resource gauges/counters without credentials:

- `platform_operations_queued{kind}` and
  `platform_operation_oldest_age_seconds{kind}` show pending work and queue age.
- `platform_operation_duration_seconds_sum/count{kind,outcome}` provide average
  observed operation duration without claiming histogram buckets.
- `platform_resources{status}`, `platform_resources_overdue_cleanup_total`, and
  `platform_orphaned_resources` help find overdue cleanup and reconciliation drift.
- `platform_worker_claim_retries_total` counts retries and
  `platform_reserved_cpu_millis`, `platform_reserved_memory_bytes`, and
  `platform_reserved_storage_bytes` show reservations.

Metrics are for operational trend and alerting, not an authorization or quota
source. Keep private infrastructure identifiers out of metric labels.

## Control-plane backup and isolated restore

Backups contain the platform control-plane PostgreSQL database, not developer DB
data volumes. Developer database retention/backup belongs to a separately
approved product policy. For the optional AWS target, pass the public age
recipient and Terraform backup bucket to Ansible with `backup_enabled=true`; this
installs a daily systemd timer that encrypts the dump and uploads it to the
private S3 `control-plane/` prefix using the EC2 instance role. The bucket retains
current backups for 90 days and noncurrent object versions for 30 days. The host
role can upload but cannot list or delete backup objects. Check timer and outcome
with `systemctl list-timers platform-control-plane-backup.timer` and
`journalctl -u platform-control-plane-backup.service`; never print secret files.

For a local backup, install `age`, make an operator-controlled age recipient
available, then run:

```sh
AGE_RECIPIENT='age1...' ops/hosting/scripts/backup-control-plane.sh /secure/backups
```

The script uses `pg_dump` from the Compose PostgreSQL container, encrypts the
temporary dump directly to an age artifact, removes the plaintext temporary file,
and writes a checksum. Store the encrypted artifact in an approved backup target
and keep the private age identity in a separate approved key-custody system. Do
not store the identity next to the archive. The host timer uses this same script
and removes local encrypted artifacts only after both the backup and checksum
are uploaded successfully.

Restore into an isolated database name only. Stop API/workers for a coordinated
recovery exercise, verify the archive and key out of band, then run:

```sh
AGE_IDENTITY_FILE=/secure/keys/platform-backup-identity.txt \
  ops/hosting/scripts/restore-control-plane.sh \
  /secure/backups/control-plane-<timestamp>.dump.age
```

The restore script refuses to overwrite a target database, validates decryptability
before creating an isolated, network-disabled PostgreSQL container with no shared
volume, and reports the restored Alembic revision. It does not switch the active
API database, delete the failed database, or claim provider reconciliation has
completed. After a real recovery, keep resource workers stopped until the
restored keys/installation ID are verified, compare control-plane ownership to
provider-owned containers, run the implemented reconciliation workflow, and
review each orphan/late operation before cleanup. The P1 worker reconciliation
acceptance must be demonstrated before treating this runbook as a proven disaster
recovery procedure.

## Optional AWS target and teardown

The AWS configuration and its protected-state bootstrap are in
[`ops/hosting/terraform/README.md`](../ops/hosting/terraform/README.md). Review the cost and
network plan before any apply. The sample target is one Docker host; it is not a
managed database service, autoscaling platform, or high-availability design.
GitHub must use the narrow OIDC roles and required `production` environment; do
not create long-lived access keys.

The EC2 control-plane volume is a separately encrypted, `prevent_destroy` EBS
volume. Initial setup requires an explicit SSM command to initialize that blank
volume; ordinary startup and host replacement only mount the expected filesystem.
Ansible SSH access requires an existing key pair and approved CIDR. SSM remains available for approved host administration; application delivery is not implemented.

Before tearing down a host, stop new requests, inspect and remove developer DBs
through the platform's owned-resource lifecycle, create and verify a protected
control-plane backup, and inspect retained EBS/ECR costs. Review the Terraform
destroy plan separately. Do not prune host Docker volumes or remove the state
bucket as a side effect of application rollback or routine Ansible shutdown.
