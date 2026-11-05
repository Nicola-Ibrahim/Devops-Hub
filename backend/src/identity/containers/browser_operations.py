"""Compatibility exports for existing host and integration-test imports."""

from identity.infra.browser_operations import BrowserIdentityService, authenticate_browser_operation

__all__ = ["BrowserIdentityService", "authenticate_browser_operation"]
