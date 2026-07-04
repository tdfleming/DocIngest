"""Tests for the docingest CLI command dispatch (client mocked)."""

from __future__ import annotations

from docingest import cli


class FakeClient:
    def __init__(self, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def search(self, query, limit=10, rerank=True):
        return {
            "results": [{"score": 0.5, "heading_chain": ["A"], "chunk_text": "hello world"}],
            "search_time_ms": 3,
        }

    def get_document(self, doc_id):
        return {"id": doc_id, "status": "complete", "source_ref": "f.pdf",
                "chunk_count": 2, "error": None}

    def list_documents(self, status=None, per_page=50):
        return {"documents": [{"id": "1", "status": "complete", "chunk_count": 2,
                               "source_ref": "f.pdf"}], "total": 1}

    def health(self):
        return {"status": "healthy", "checks": {"mongodb": "ok"}}


def test_search_command(monkeypatch, capsys):
    monkeypatch.setattr(cli, "DocIngestClient", FakeClient)
    rc = cli.main(["search", "hello"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "hello world" in out
    assert "results in 3ms" in out


def test_status_command(monkeypatch, capsys):
    monkeypatch.setattr(cli, "DocIngestClient", FakeClient)
    rc = cli.main(["status", "abc"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "complete" in out


def test_list_command_with_json_flag(monkeypatch, capsys):
    monkeypatch.setattr(cli, "DocIngestClient", FakeClient)
    rc = cli.main(["--json", "list"])
    out = capsys.readouterr().out
    assert rc == 0
    assert '"total": 1' in out


def test_health_healthy_returns_zero(monkeypatch, capsys):
    monkeypatch.setattr(cli, "DocIngestClient", FakeClient)
    assert cli.main(["health"]) == 0
    assert "healthy" in capsys.readouterr().out
