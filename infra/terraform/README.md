# Optional AWS Docker host

The AWS target is optional. The local Docker demonstration has no AWS credential
dependency. Terraform creates one Ubuntu host, a VPC/public subnet, HTTPS/HTTP
ingress, optional key-pair/CIDR-restricted SSH, an encrypted root disk, a separate
encrypted persistent Docker data disk, one immutable ECR repository, instance ECR-pull/SSM roles, and narrowly trusted GitHub OIDC publish
and production-deploy roles. It does not open PostgreSQL ports to the Internet.
Ansible configures Nginx/TLS and the host; CI builds and publishes image digests;
the platform worker owns per-developer databases.

## Protected state bootstrap

Use an operator account with the required S3 permissions to provision the state
bucket once. Keep the bootstrap state in an approved administrative location and
back it up; this directory intentionally has no remote backend. Review cost and
retention before applying either configuration.

```sh
cd infra/terraform/state-bootstrap
terraform init
terraform plan -var='state_bucket_name=<globally-unique-name>'
# Apply only after reviewing the plan and approving AWS access.
```

The bucket has public access blocked, versioning, server-side encryption, a TLS
only policy, incomplete multipart cleanup, and `prevent_destroy`. S3 native state
locking is enabled by Terraform 1.10+ with `use_lockfile=true`.

## Host plan inputs

Create a private tfvars file from `aws-platform/terraform.tfvars.example`; do not
commit it. Set the exact GitHub owner/repository and retrieve/verify the current
OIDC TLS thumbprint using AWS/GitHub documentation. `ssh_ingress_cidrs` defaults
to empty, which disables SSH ingress. If Ansible SSH setup is required, configure
an existing EC2 key pair with `ssh_key_name` and restrict ingress to the operator
VPN /32 or another approved CIDR. SSM is the deploy path and database ports are
never public.

```sh
cd infra/terraform/aws-platform
terraform init -backend-config=backend.hcl
terraform fmt -check -recursive
terraform plan -var-file=private.tfvars
```

Configure GitHub repository variables from Terraform outputs:

- `AWS_REGION`
- `AWS_ACCOUNT_ID`
- `AWS_ECR_REPOSITORY` (repository URL)
- `AWS_PUBLISH_ROLE_ARN`
- `AWS_DEPLOY_ROLE_ARN`
- `PLATFORM_INSTANCE_ID`

Keep the `backup_bucket_name` output for Ansible's optional scheduled backup role.

Create a protected GitHub environment named `production` with required human
review. The publish role accepts the `main` branch subject; the deploy role
accepts only the `production` environment subject. Protect the environment with
branch/reviewer rules because the environment subject intentionally excludes the
branch name. Never put AWS access keys or image registry credentials in GitHub
secrets.

The EC2 instance role grants SSM managed-instance access, pull-only ECR access to
the platform repository, and put-only access to the encrypted backup prefix. The
GitHub publisher can push and scan that one ECR repo;
the production deployer can issue SSM commands to the configured instance. The
ECR authorization-token action requires `Resource: "*"`; image layer operations
are scoped to the single repository.

## Persistent data and initial host setup

The host's Docker data root is mounted on a separately encrypted gp3 EBS volume
with `prevent_destroy` and a final snapshot. Platform DB volumes live below that
Docker root, so replacement of the EC2 root disk does not silently erase the
control plane. Instance user data waits for the exact EBS volume ID and mounts
only an ext4 filesystem carrying the expected label. On first creation, the blank
volume is not formatted automatically. After reviewing the Terraform output and
volume ID, explicitly initialize it through SSM:

```sh
aws ssm send-command \
  --instance-ids <instance-id> \
  --document-name AWS-RunShellScript \
  --parameters 'commands=["sudo /usr/local/sbin/initialize-platform-data-volume --initialize-empty-volume"]'
```

The initializer checks the exact attached volume ID, filesystem signatures and
mount path before formatting a blank device. Normal boot and host replacement use
`--mount-existing`; an existing filesystem with the wrong label fails closed.
Existing Docker data on an already-running host is not migrated automatically:
back it up and perform a separately reviewed copy/restore before switching Docker's
data root.

The data-volume resource has `prevent_destroy`, so ordinary Terraform destroy
plans stop instead of deleting the only persistent copy. Teardown requires a
separate reviewed backup/snapshot procedure and an explicit lifecycle change.

The optional private S3 backup bucket has versioning, server-side encryption,
public-access blocks, a TLS-only policy, a 90-day current-object lifecycle and
30-day noncurrent-version retention. The instance role can only write below
`control-plane/`; it cannot list or delete backup objects. Supply the public age
recipient and bucket output to Ansible with `backup_enabled=true` to install a
daily systemd timer. The private age identity remains outside the host and bucket.

## Safe teardown

Before destroying the host, export any platform control-plane data using the
backup procedure in `docs/operations.md`, stop new resource requests, inspect
and remove developer resources through the platform lifecycle API, then review
the Terraform destroy plan and expected EC2/EBS/EIP costs. Preserve or deliberately
remove the Terraform state bucket through a separate reviewed process. Terraform
does not manage cleanup of individual developer DB containers or data volumes.
