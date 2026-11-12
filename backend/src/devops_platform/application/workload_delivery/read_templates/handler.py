"""Read the approved application template catalog."""

from devops_platform.application.workload_delivery.read_templates.query import ReadTemplates
from devops_platform.application.workload_delivery.shared.models import TemplateVersion
from devops_platform.application.workload_delivery.shared.ports import TemplateCatalog


class ReadTemplatesHandler:
    def __init__(self, templates: TemplateCatalog) -> None:
        self.templates = templates

    async def execute(self, query: ReadTemplates) -> tuple[TemplateVersion, ...]:
        del query
        return self.templates.list_templates()
