"""Asynchronous operation progress routes."""

from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Depends

from api.core.dependencies import platform_access
from api.platform.operations.schemas import OperationView
from devops_hub.platform.application.database_provisioning.read_resources.query import ReadOperation
from devops_hub.platform.application.module import DeveloperPlatformModule
from devops_hub.platform.application.shared.dto import AccessContext
from devops_hub.platform.authorization import authorize_platform_action

router = APIRouter()
Access = Annotated[AccessContext, Depends(platform_access)]


@router.get("/operations/{operation_id}", response_model=OperationView, tags=["operations"])
@inject
async def operation(
    operation_id: UUID, access: Access, module: FromDishka[DeveloperPlatformModule]
) -> OperationView:
    message = ReadOperation(access, operation_id)
    authorize_platform_action(message)
    result = await module.query(message)
    return OperationView.model_validate(asdict(result))
