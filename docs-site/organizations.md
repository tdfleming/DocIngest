# Organizations

An **organization** is the tenant boundary. Its id doubles as the `tenant_id` that
scopes all data (Qdrant collections, blob prefixes, Mongo queries). Users join orgs
through memberships with a role: **OWNER**, **ADMIN**, or **MEMBER**.

A user gets their first org from [self-serve signup](getting-started.md); the JWT carries
the active org. These endpoints (JWT-authenticated) manage orgs and members.

## Endpoints

| Method | Path | Who | Description |
|--------|------|-----|-------------|
| `GET` | `/v1/orgs` | any user | List orgs you belong to (with your role) |
| `POST` | `/v1/orgs` | any user | Create an org (you become OWNER) |
| `GET` | `/v1/orgs/current` | member | The active org from your JWT |
| `GET` | `/v1/orgs/{id}` | member | Org details |
| `GET` | `/v1/orgs/{id}/members` | member | List members |
| `POST` | `/v1/orgs/{id}/members` | OWNER/ADMIN | Add an existing user (by username) |
| `PATCH` | `/v1/orgs/{id}/members/{user_id}` | OWNER/ADMIN | Change a member's role |
| `DELETE` | `/v1/orgs/{id}/members/{user_id}` | OWNER/ADMIN | Remove a member |

## Roles

- **OWNER** — full control; an org always keeps at least one owner (the API blocks demoting or removing the last one).
- **ADMIN** — manage members and settings.
- **MEMBER** — access org data, but can't manage membership.

## Keys vs. members

Members authenticate with **JWTs** (people). Machine/data-plane access uses **API keys**
scoped to the org (`tenant_id` = org id) with least-privilege
[scopes](api-reference.md) — issue those from the admin API.
