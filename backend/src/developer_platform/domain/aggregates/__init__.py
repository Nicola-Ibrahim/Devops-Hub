"""Aggregate roots that protect platform lifecycle invariants."""

from developer_platform.domain.aggregates.application_delivery import ApplicationDelivery
from developer_platform.domain.aggregates.resource_lifecycle import ResourceLifecycle

__all__ = ["ApplicationDelivery", "ResourceLifecycle"]
