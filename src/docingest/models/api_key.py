"""API key scopes.

Scopes let an org issue least-privilege keys. A key with **no** scopes (legacy
keys created before this feature) or the ``admin`` scope has full access, so
existing keys keep working unchanged.
"""

from __future__ import annotations

from enum import StrEnum


class ApiKeyScope(StrEnum):
    READ = "read"  # search + read documents/graph
    INGEST = "ingest"  # create / delete / reprocess documents
    ADMIN = "admin"  # superset — includes read, ingest, and admin operations


def key_has_scope(scopes: list[str] | None, required: ApiKeyScope) -> bool:
    """Whether a key with ``scopes`` may perform an action requiring ``required``.

    A key with no scopes (legacy/full) or the ADMIN scope passes any check.
    """
    if not scopes:
        return True
    if ApiKeyScope.ADMIN in scopes:
        return True
    return required in scopes
