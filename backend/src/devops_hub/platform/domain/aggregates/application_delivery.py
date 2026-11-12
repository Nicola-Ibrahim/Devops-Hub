"""Aggregate root for application delivery state and retry decisions."""

from dataclasses import dataclass, replace
from datetime import datetime

from devops_hub.platform.domain.entities.application import Application, DeliveryStep
from devops_hub.platform.domain.errors import DomainError


@dataclass(frozen=True, slots=True)
class ApplicationDelivery:
    application: Application
    steps: tuple[DeliveryStep, ...] = ()

    def attach_step(self, step: DeliveryStep) -> "ApplicationDelivery":
        if self.application.status in {"deleting", "deleted"}:
            raise DomainError("Application cleanup is in progress or complete.")
        if any(existing.id == step.id for existing in self.steps):
            return self
        return ApplicationDelivery(
            replace(self.application, status="pending", updated_at=step.updated_at),
            (*self.steps, step),
        )

    def retry(self, step_id: object, now: datetime) -> "ApplicationDelivery":
        selected = next((step for step in self.steps if step.id == step_id), None)
        if selected is None:
            raise DomainError("Delivery step was not found.")
        if selected.status == "succeeded":
            return self
        if (
            self.application.status in {"deleting", "deleted"}
            and selected.kind != "preview_cleanup"
        ):
            raise DomainError("Application cleanup is in progress or complete.")
        updated = replace(selected, status="pending", error_code=None, updated_at=now)
        return ApplicationDelivery(
            replace(
                self.application,
                status="deleting" if selected.kind == "preview_cleanup" else "pending",
                updated_at=now,
            ),
            tuple(updated if step.id == selected.id else step for step in self.steps),
        )
