"""Execute a claimed delivery effect outside SQL transactions."""

from uuid import UUID

from developer_platform.application.workload_delivery.attach_database.command import (
    ResourceAttachmentCommand,
)
from developer_platform.application.workload_delivery.shared.models import (
    DeliveryClaim,
    DeliveryResult,
)
from developer_platform.application.workload_delivery.shared.ports import (
    ApplicationDeliveryFailure,
    ApplicationDeployer,
    ApprovedImageCatalog,
    RepositoryProvisioner,
    ResourceProvisioner,
    TemplateCatalog,
)


class ExecuteDeliveryStepHandler:
    def __init__(
        self,
        templates: TemplateCatalog,
        images: ApprovedImageCatalog,
        repositories: RepositoryProvisioner | None,
        resources: ResourceProvisioner | None,
        deployer: ApplicationDeployer | None,
    ) -> None:
        self.templates = templates
        self.images = images
        self.repositories = repositories
        self.resources = resources
        self.deployer = deployer

    async def execute(self, claim: DeliveryClaim) -> DeliveryResult:
        repositories = self.repositories
        resources = self.resources
        deployer = self.deployer
        if claim.kind == "repository":
            if repositories is None:
                raise ApplicationDeliveryFailure("repository_provider_disabled")
            template = self.templates.get(claim.template_id, claim.template_version)
            files = self.templates.render(
                claim.template_id,
                claim.template_version,
                {"application_name": claim.application_name},
            )
            url = await repositories.create_repository(
                project_id=claim.project_id,
                application_id=claim.application_id,
                name=claim.application_name,
                template=template,
                files=files,
                idempotency_key=claim.idempotency_key,
            )
            return DeliveryResult(repository_url=url)
        if claim.kind == "resource":
            if resources is None:
                raise ApplicationDeliveryFailure("resource_provider_disabled")
            ttl_raw = claim.payload.get("ttl_seconds", 0)
            if not isinstance(ttl_raw, int) or isinstance(ttl_raw, bool):
                raise ApplicationDeliveryFailure("resource_request_invalid", retryable=False)
            command = ResourceAttachmentCommand(
                template_id=str(claim.payload.get("template_id", "")),
                version=str(claim.payload.get("version", "")),
                target_id=str(claim.payload.get("target_id", "")),
                size_id=str(claim.payload.get("size_id", "")),
                ttl_seconds=ttl_raw,
            )
            resource_id = await resources.request(
                project_id=claim.project_id,
                environment_id=claim.environment_id,
                owner_id=claim.owner_id,
                command=command,
                idempotency_key=claim.idempotency_key,
            )
            # Persist the stable resource ID before readiness polling. The SQL worker
            # adapter retries this same idempotent request until the owned row is ready;
            # close/expiry can then always enqueue cleanup with the known ID.
            return DeliveryResult(resource_id=resource_id)
        if claim.kind == "deployment":
            if deployer is None:
                raise ApplicationDeliveryFailure("deployment_target_disabled")
            image_digest = str(claim.payload.get("image_digest", ""))
            target_id = str(claim.payload.get("target_id", "local"))
            if not self.images.is_approved(image_digest, target_id):
                raise ApplicationDeliveryFailure("image_not_approved", retryable=False)
            deployment_id = UUID(str(claim.payload["deployment_id"]))
            resource_id_raw = claim.payload.get("resource_id")
            deployment_resource_id = UUID(str(resource_id_raw)) if resource_id_raw else None
            url, reference = await deployer.deploy(
                project_id=claim.project_id,
                application_id=claim.application_id,
                deployment_id=deployment_id,
                image_digest=image_digest,
                target_id=target_id,
                resource_id=deployment_resource_id,
                idempotency_key=claim.idempotency_key,
            )
            return DeliveryResult(
                deployment_id=deployment_id,
                deployment_url=url,
                provider_reference=reference,
            )
        if claim.kind == "template_update":
            if repositories is None:
                raise ApplicationDeliveryFailure("repository_provider_disabled")
            repository_url = str(claim.payload.get("repository_url", ""))
            files = self.templates.render(
                claim.template_id,
                claim.template_version,
                {"application_name": claim.application_name},
            )
            pull_request_url = await repositories.create_update_pull_request(
                repository_url=repository_url,
                branch=f"platform/template-{claim.template_version}",
                files=files,
                idempotency_key=claim.idempotency_key,
            )
            return DeliveryResult(provider_reference=pull_request_url)
        if claim.kind == "preview_cleanup":
            if claim.payload.get("remove_deployments") is True:
                if deployer is None:
                    raise ApplicationDeliveryFailure("deployment_target_disabled")
                await deployer.remove(claim.project_id, claim.application_id, claim.idempotency_key)
            cleanup_resource_id = claim.payload.get("resource_id")
            if cleanup_resource_id is not None:
                if resources is None:
                    raise ApplicationDeliveryFailure("resource_provider_disabled")
                await resources.delete(
                    claim.project_id,
                    claim.owner_id,
                    UUID(str(cleanup_resource_id)),
                    claim.idempotency_key + ":resource",
                )
            return DeliveryResult()
        raise ApplicationDeliveryFailure("unknown_delivery_step", retryable=False)
