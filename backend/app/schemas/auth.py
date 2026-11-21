from __future__ import annotations

import re
from enum import Enum
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

ACCOUNT_USERNAME_PATTERN = re.compile(r"[A-Za-z0-9._-]{3,64}")


def is_valid_account_email(email: str) -> bool:
    return len(email) <= 255 and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) is not None


class UserRole(str, Enum):
    ANALYST = "Analyst"
    TEAM_LEAD = "TeamLead"
    ADMIN = "Admin"


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1)


class UserDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: str
    role: UserRole
    is_active: bool
    created_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserDTO

