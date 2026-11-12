"""Aggregate roots that protect platform lifecycle invariants."""

from devops_platform.domain.aggregates.application_delivery import ApplicationDelivery
from devops_platform.domain.aggregates.resource_lifecycle import ResourceLifecycle

__all__ = ["ApplicationDelivery", "ResourceLifecycle"]
