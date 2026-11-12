"""HTTP request models for project membership management."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class MembershipBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["developer", "admin"]
