# ruff: noqa: F401
"""Safe local adapters for approved templates and explicitly configured providers."""

import base64
import hashlib
import hmac
import json
import re
from pathlib import Path
from typing import Any
from uuid import UUID

from devops_platform.application.workload_delivery.shared.models import (
    GeneratedFile,
    TemplateVersion,
)
from devops_platform.application.workload_delivery.shared.ports import (
    ApplicationDeliveryFailure,
    ApprovedImageCatalog,
    RequestFingerprint,
    TemplateCatalog,
    WebhookSignatureVerifier,
)


class FilesystemTemplateCatalog(TemplateCatalog):
    """Reads versioned templates without allowing path traversal or symlink escape."""

    _TOKEN = re.compile(r"__[A-Z][A-Z0-9_]{1,63}__")
    _MAX_FILES = 500
    _MAX_FILE_BYTES = 1024 * 1024

    def __init__(self, root: Path, workflow_repository: str | None = None) -> None:
        self.root = root.resolve()
        self.workflow_repository = workflow_repository

    def list_templates(self) -> tuple[TemplateVersion, ...]:
        found: list[TemplateVersion] = []
        if not self.root.is_dir():
            return ()
        for descriptor in sorted(self.root.glob("*/[0-9]*.*/template.json")):
            try:
                found.append(self._metadata(json.loads(descriptor.read_text(encoding="utf-8"))))
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return tuple(found)

    def get(self, template_id: str, version: str) -> TemplateVersion:
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", template_id) or not re.fullmatch(
            r"[0-9]+\.[0-9]+\.[0-9]+", version
        ):
            raise ApplicationDeliveryFailure("template_not_found", retryable=False)
        directory = (self.root / template_id / version).resolve()
        if self.root not in directory.parents or not directory.is_dir():
            raise ApplicationDeliveryFailure("template_not_found", retryable=False)
        descriptor = directory / "template.json"
        try:
            if descriptor.is_symlink():
                raise ApplicationDeliveryFailure("template_invalid", retryable=False)
            metadata = self._metadata(json.loads(descriptor.read_text(encoding="utf-8")))
        except (OSError, ValueError, KeyError, TypeError):
            raise ApplicationDeliveryFailure("template_invalid", retryable=False) from None
        if metadata.template_id != template_id or metadata.version != version:
            raise ApplicationDeliveryFailure("template_invalid", retryable=False)
        return metadata

    def render(
        self, template_id: str, version: str, values: dict[str, str]
    ) -> tuple[GeneratedFile, ...]:
        self.get(template_id, version)
        if self.workflow_repository is None or not re.fullmatch(
            r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", self.workflow_repository
        ):
            raise ApplicationDeliveryFailure("template_workflow_not_configured", retryable=False)
        directory = self.root / template_id / version
        result: list[GeneratedFile] = []
        paths = sorted(path for path in directory.rglob("*") if path.is_file())
        if len(paths) > self._MAX_FILES:
            raise ApplicationDeliveryFailure("template_too_large", retryable=False)
        manifest: dict[str, str] = {}
        for path in paths:
            if path.is_symlink() or path.name == "template.json":
                if path.is_symlink():
                    raise ApplicationDeliveryFailure("template_invalid", retryable=False)
                continue
            resolved = path.resolve()
            if directory.resolve() not in resolved.parents:
                raise ApplicationDeliveryFailure("template_invalid", retryable=False)
            relative = path.relative_to(directory).as_posix()
            if relative.startswith("/") or ".." in Path(relative).parts:
                raise ApplicationDeliveryFailure("template_invalid", retryable=False)
            raw = path.read_bytes()
            if len(raw) > self._MAX_FILE_BYTES:
                raise ApplicationDeliveryFailure("template_too_large", retryable=False)
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError:
                content = None
            if content is not None:
                content = content.replace(
                    "__PLATFORM_WORKFLOWS_REPOSITORY__", self.workflow_repository
                )
                for key, value in values.items():
                    token_key = key.upper()
                    if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", token_key):
                        raise ApplicationDeliveryFailure("template_value_invalid", retryable=False)
                    if "\n" in value or "\r" in value:
                        raise ApplicationDeliveryFailure("template_value_invalid", retryable=False)
                    content = content.replace(f"__{token_key}__", value)
                if self._TOKEN.search(content):
                    raise ApplicationDeliveryFailure("template_value_missing", retryable=False)
                raw = content.encode("utf-8")
            digest = hashlib.sha256(raw).hexdigest()
            manifest[relative] = digest
            result.append(GeneratedFile(relative, raw, digest))
        provenance = {
            "template_id": template_id,
            "template_version": version,
            "managed_files": manifest,
        }
        raw_manifest = (json.dumps(provenance, sort_keys=True, indent=2) + "\n").encode()
        result.append(
            GeneratedFile(
                ".platform-template.json", raw_manifest, hashlib.sha256(raw_manifest).hexdigest()
            )
        )
        return tuple(result)

    @staticmethod
    def _metadata(data: Any) -> TemplateVersion:
        if not isinstance(data, dict):
            raise ValueError("invalid template descriptor")
        return TemplateVersion(
            template_id=str(data["id"]),
            version=str(data["version"]),
            language=str(data["language"]),
            display_name=str(data["display_name"]),
            description=str(data["description"]),
        )
