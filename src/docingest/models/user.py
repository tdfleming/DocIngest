from enum import StrEnum

from pydantic import BaseModel, Field


class UserRole(StrEnum):
    ADMIN = "admin"
    VIEWER = "viewer"


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class UserResponse(BaseModel):
    id: str
    username: str
    role: UserRole
    created_at: str


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.VIEWER


class SignupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)
    organization_name: str = Field(min_length=2, max_length=100)


class UpdateUserRequest(BaseModel):
    password: str | None = Field(None, min_length=8, max_length=128)
    role: UserRole | None = None
