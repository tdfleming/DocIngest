"""Organization & membership models.

An **organization** is the top-level tenant boundary for the SaaS layer. Its id
(the Mongo ``_id`` as a string) is used directly as the ``tenant_id`` that scopes
all existing data isolation (Qdrant collections, MinIO prefixes, Mongo queries),
so the org model layers on top of the current tenancy without changing it.

Users join organizations through **memberships** carrying a role.
"""

from enum import StrEnum

from pydantic import BaseModel, Field

SLUG_PATTERN = r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$"


class OrgRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class Organization(BaseModel):
    id: str
    name: str
    slug: str
    owner_user_id: str
    created_at: str


class OrganizationMembership(BaseModel):
    id: str
    org_id: str
    user_id: str
    role: OrgRole
    created_at: str


# --- API request/response models (used by later slices) ---


class CreateOrganizationRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    slug: str | None = Field(default=None, min_length=2, max_length=63, pattern=SLUG_PATTERN)


class OrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str
    # The requesting user's role in this org, when resolved through a membership.
    role: OrgRole | None = None
    created_at: str


class MemberResponse(BaseModel):
    user_id: str
    role: OrgRole
    created_at: str
