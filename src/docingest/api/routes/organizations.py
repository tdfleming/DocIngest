"""Organization management routes (JWT-authenticated).

Users list/create orgs; OWNER/ADMIN members manage membership. Path-based
endpoints verify the caller's membership in the org named in the path.
"""

from bson import ObjectId
from fastapi import APIRouter, HTTPException

from docingest.api.auth import CurrentOrg, CurrentUser
from docingest.db.mongodb import get_db
from docingest.db.organizations import (
    add_membership,
    count_org_role,
    create_organization,
    get_membership,
    get_organization,
    list_org_members,
    list_user_organizations,
    remove_membership,
    update_member_role,
)
from docingest.models.organization import (
    AddMemberRequest,
    CreateOrganizationRequest,
    MemberResponse,
    OrganizationResponse,
    OrgRole,
    UpdateMemberRequest,
)

router = APIRouter(prefix="/orgs")


def _org_response(doc: dict, role: OrgRole | None = None) -> OrganizationResponse:
    return OrganizationResponse(
        id=str(doc["_id"]),
        name=doc["name"],
        slug=doc["slug"],
        role=role or doc.get("role"),
        created_at=doc["created_at"].isoformat(),
    )


async def _require_member(db, org_id: str, user_id: str) -> dict:
    membership = await get_membership(db, org_id, user_id)
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    return membership


def _require_manager(membership: dict) -> None:
    if membership["role"] not in (OrgRole.OWNER, OrgRole.ADMIN):
        raise HTTPException(status_code=403, detail="Requires OWNER or ADMIN role")


@router.get("")
async def list_my_orgs(user: CurrentUser):
    """List the organizations the current user belongs to."""
    db = await get_db()
    orgs = await list_user_organizations(db, user["user_id"])
    return [_org_response(o) for o in orgs]


@router.post("", status_code=201)
async def create_org(body: CreateOrganizationRequest, user: CurrentUser):
    """Create a new organization; the caller becomes its OWNER."""
    db = await get_db()
    org = await create_organization(db, body.name, owner_user_id=user["user_id"], slug=body.slug)
    return _org_response(org, role=OrgRole.OWNER)


@router.get("/current")
async def get_current_org(org: CurrentOrg):
    """The active organization resolved from the JWT."""
    db = await get_db()
    doc = await get_organization(db, org["org_id"])
    if not doc:
        raise HTTPException(status_code=404, detail="Organization not found")
    return _org_response(doc, role=org["role"])


@router.get("/{org_id}")
async def get_org(org_id: str, user: CurrentUser):
    db = await get_db()
    membership = await _require_member(db, org_id, user["user_id"])
    doc = await get_organization(db, org_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Organization not found")
    return _org_response(doc, role=membership["role"])


@router.get("/{org_id}/members")
async def get_members(org_id: str, user: CurrentUser):
    db = await get_db()
    await _require_member(db, org_id, user["user_id"])
    members = await list_org_members(db, org_id)
    ids = [ObjectId(m["user_id"]) for m in members if ObjectId.is_valid(m["user_id"])]
    users = await db.users.find({"_id": {"$in": ids}}, {"username": 1}).to_list(1000)
    names = {str(u["_id"]): u.get("username") for u in users}
    return [
        MemberResponse(
            user_id=m["user_id"],
            username=names.get(m["user_id"]),
            role=m["role"],
            created_at=m["created_at"].isoformat(),
        )
        for m in members
    ]


@router.post("/{org_id}/members", status_code=201)
async def add_member(org_id: str, body: AddMemberRequest, user: CurrentUser):
    """Add an existing user (by username) to the org. Requires OWNER/ADMIN."""
    db = await get_db()
    _require_manager(await _require_member(db, org_id, user["user_id"]))
    target = await db.users.find_one({"username": body.username})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    membership = await add_membership(db, org_id, str(target["_id"]), body.role)
    return MemberResponse(
        user_id=str(target["_id"]),
        username=target["username"],
        role=membership["role"],
        created_at=membership["created_at"].isoformat(),
    )


@router.patch("/{org_id}/members/{member_id}")
async def change_member_role(
    org_id: str, member_id: str, body: UpdateMemberRequest, user: CurrentUser
):
    db = await get_db()
    _require_manager(await _require_member(db, org_id, user["user_id"]))
    target = await get_membership(db, org_id, member_id)
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")
    if (
        target["role"] == OrgRole.OWNER
        and body.role != OrgRole.OWNER
        and await count_org_role(db, org_id, OrgRole.OWNER) <= 1
    ):
        raise HTTPException(status_code=400, detail="Cannot demote the last owner")
    await update_member_role(db, org_id, member_id, body.role)
    return {"user_id": member_id, "role": str(body.role)}


@router.delete("/{org_id}/members/{member_id}")
async def remove_member(org_id: str, member_id: str, user: CurrentUser):
    db = await get_db()
    _require_manager(await _require_member(db, org_id, user["user_id"]))
    target = await get_membership(db, org_id, member_id)
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")
    if (
        target["role"] == OrgRole.OWNER
        and await count_org_role(db, org_id, OrgRole.OWNER) <= 1
    ):
        raise HTTPException(status_code=400, detail="Cannot remove the last owner")
    await remove_membership(db, org_id, member_id)
    return {"user_id": member_id, "status": "removed"}
