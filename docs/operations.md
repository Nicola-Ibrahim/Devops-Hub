# Platform operations

This guide describes the local Docker demo and the optional single-host AWS
target. Terraform provisions the host and its IAM/network boundary; Ansible
configures the host; CI builds and publishes immutable platform images; the API
and worker own developer-requested PostgreSQL resources. Publishing an image is
not a deployment. No AWS account is needed for the local runtime.

## Local Docker demo

Requirements: Docker Engine/Desktop with Compose v2, Python 3.12/`uv` for local
backend checks, and Node.js 22/npm for dashboard checks. Start Docker before
starting Compose.

```sh
scripts/ops/create-local-secrets.sh
scripts/ops/compose-up.sh
```

The secret bootstrap creates synthetic local values under `.local/secrets/` with
mode `0600`. The Prometheus scrape token is mounted read-only into its container
and is only traversable on the host through the directory's mode `0700`. The
bootstrap never prints values and never changes an existing complete secret set.
If the set is partial, it fails closed; a legacy complete six-key set gets only
the missing metrics token added without changing existing values. The repository
root ignores `.local/`. Keep the resource
encryption key and installation ID stable for as long as encrypted control-plane
records are retained. Key rotation needs an explicit re-encryption and DB password
rotation procedure.

Compose starts PostgreSQL 16, an explicit Alembic migration job, the FastAPI API,
the worker and the Next.js dashboard. The API is published to host loopback on
8000, the dashboard on 3000, and provisioned developer PostgreSQL endpoints are
advertised on host loopback. PostgreSQL control-plane data uses a named volume.
`docker compose --profile app down` stops containers and preserves volumes;
never add `-v` or run `docker system prune` as routine cleanup.

Only the worker receives `/var/run/docker.sock`, because it is the component that
manages local DB containers. Access to that socket is equivalent to host root;
keep this demo on a trusted developer machine. The script discovers the socket's
group ID for the worker without making the API privileged. Do not publish the API
or worker Docker socket to the public network.

Compose mounts source secret files read-only. A small root entrypoint copies only
the configured `_FILE` values from `PLATFORM_SECRET_FILES_ROOT` (default
`/run/secrets`) into each API/worker/migration container's ephemeral `/run` tmpfs,
sets mode `0400` and ownership to the fixed non-root service UID, then drops
privileges. Worker supplementary groups retain only the configured Docker socket
GID; the API does not receive that group or socket.

The backend accepts runtime environment values and secret-file paths, so a future
Vault agent can inject values directly or render files beneath a mounted trusted
directory and set `PLATFORM_SECRET_FILES_ROOT` plus the matching `*_FILE` paths.
Never include secret values in Compose interpolation files or print resolved
`docker compose config` output.

The worker's `PLATFORM_LOCAL_PROVIDER_ENABLED` setting defaults to false. Enable
it only after the local provider readiness, credential isolation, host network
connection, retry/restart and cleanup acceptance checks have passed:

```sh
PLATFORM_LOCAL_PROVIDER_ENABLED=true scripts/ops/compose-up.sh
```

The default catalog remains non-requestable until that acceptance is complete.
The API's `/health/live` and `/health/ready` endpoints report process and DB/schema
readiness. Readiness depends on the explicitly applied schema revision; API
startup never migrates the shared database.

## Host setup and TLS

Install the pinned Ansible collections once, then syntax-check before applying to
a disposable Ubuntu host:

```sh
cd infra/ansible
ansible-galaxy collection install -r requirements.yml
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

The optional Doppler role is disabled unless explicitly enabled. If used, its
service token is hidden from Ansible output and downloaded environment files are
written with mode `0600`; the local Compose demo uses generated files instead.

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

The separate `Deploy Platform` workflow is manual and uses a protected GitHub
`production` environment. Supply both exact image digests from the successful
publish run. Deployment blocks unless the operator confirms migration
compatibility with the previous app version. A reviewer must confirm that every
database change follows expand/contract: additive schema first, code compatible
with old and new schema, and destructive contraction only in a later reviewed
release after rollback is no longer needed. There is no automatic Alembic
downgrade.

The deploy role obtains short-lived AWS credentials through GitHub OIDC and sends
the digest-only command to the configured EC2 instance through SSM. The EC2 role
pulls from its one ECR repository. The host script captures the existing image
digests, runs the forward migration, starts images with `--no-build`, checks API
schema readiness and dashboard HTTP readiness, then records the release. If
readiness fails, it restores the prior image digests and checks the old app. It
never removes the database volume or downgrades schema. A first release has no
prior image to restore and needs operator-led recovery if it fails readiness.

The SSM deployment assumes Ansible already placed `compose.yaml` and
`scripts/ops/release.sh` on the host and an operator provisioned all seven secret
files under `/etc/devops-hub/secrets/` with mode `0400` or `0600`. Secret delivery
is intentionally a separate operator-controlled process; Terraform state and
deployment inputs do not contain application credentials. The HTTP ports are
bound only to host loopback for Nginx to proxy. No PostgreSQL port is opened in
the EC2 security group.

To inspect a release without exposing environment data, review the root-owned
`.release.env` and timestamped files under `/opt/devops-hub/releases/`; they hold
image references and the secret-directory path, not secret values. Check API and
frontend readiness endpoints and the corresponding SSM command status. Avoid
printing `docker inspect` environment, `docker compose config` output, or secret
file contents into a CI log.

## Queue monitoring

Start local Prometheus together with the application:

```sh
docker compose --profile app --profile observability up -d
```

Prometheus listens only on `127.0.0.1:9090`, scrapes the internal API `/metrics`
endpoint every 15 seconds, and retains 15 days in a separate named volume. The
alert rules cover operation age above two minutes, overdue cleanup, orphaned
resources, and repeated worker claim retries. These rules surface in Prometheus;
an Alertmanager or external paging destination still needs explicit company
configuration. Do not expose the Prometheus port publicly.

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
AGE_RECIPIENT='age1...' scripts/ops/backup-control-plane.sh /secure/backups
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
  scripts/ops/restore-control-plane-isolated.sh \
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
[`infra/terraform/README.md`](../infra/terraform/README.md). Review the cost and
network plan before any apply. The sample target is one Docker host; it is not a
managed database service, autoscaling platform, or high-availability design.
GitHub must use the narrow OIDC roles and required `production` environment; do
not create long-lived access keys.

The EC2 control-plane volume is a separately encrypted, `prevent_destroy` EBS
volume. Initial setup requires an explicit SSM command to initialize that blank
volume; ordinary startup and host replacement only mount the expected filesystem.
Ansible SSH access requires an existing key pair and approved CIDR. SSM is used
for releases after the host has been configured.

Before tearing down a host, stop new requests, inspect and remove developer DBs
through the platform's owned-resource lifecycle, create and verify a protected
control-plane backup, and inspect retained EBS/ECR costs. Review the Terraform
destroy plan separately. Do not prune host Docker volumes or remove the state
bucket as a side effect of application rollback or routine Ansible shutdown.
