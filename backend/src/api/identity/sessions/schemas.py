"""HTTP request models for session management."""

from pydantic import BaseModel, ConfigDict, Field


class PasswordBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(
        alias="currentPassword", min_length=1, max_length=1024, repr=False
    )
    new_password: str = Field(alias="newPassword", min_length=12, max_length=1024, repr=False)
