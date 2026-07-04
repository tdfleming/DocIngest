"""Smoke test for the MCP server. Skipped unless the optional `mcp` extra is installed."""

from __future__ import annotations

import pytest

pytest.importorskip("mcp")

from docingest.mcp_server import build_server  # noqa: E402


class FakeClient:
    def __init__(self, **kwargs):
        pass


def test_build_server_registers_tools_without_error():
    # build_server runs the @mcp.tool() decorators; invalid tool signatures would
    # raise here. A successful build with a runnable server is the smoke test.
    server = build_server(client=FakeClient())
    assert server is not None
    assert hasattr(server, "run")
