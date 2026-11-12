"""HTTP request models for browser authentication."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LoginBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_name: str = Field(alias="userName", min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=1024, repr=False)
    project_id: UUID | None = Field(default=None, alias="projectId")


class ProjectBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: UUID = Field(alias="projectId")
