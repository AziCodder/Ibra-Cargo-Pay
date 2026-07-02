"""Юнит-тесты storage_reconcile.reconcile_once (догон отставшего таргета из outbox)."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services import storage_reconcile, storage_service
from app.services.storage_service import S3Target


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, rows):
        self.rows = rows
        self.deleted = []
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def execute(self, _query):
        return _FakeResult(self.rows)

    async def delete(self, row):
        self.deleted.append(row)

    async def commit(self):
        self.committed = True


def _row(**kw):
    base = dict(id=1, key="uploads/a.pdf", op="put", target="secondary",
                attempts=0, last_error=None)
    base.update(kw)
    return SimpleNamespace(**base)


def _client_factory(s3):
    @asynccontextmanager
    async def _factory(target, read_timeout: int = 15):
        yield s3

    return _factory


def _targets():
    return [
        S3Target("primary", "e1", "a", "s", "r", "b1"),
        S3Target("secondary", "e2", "a", "s", "r", "b2"),
    ]


@pytest.mark.asyncio
async def test_put_row_copies_and_deletes(monkeypatch):
    session = _FakeSession([_row(op="put", target="secondary")])
    monkeypatch.setattr(storage_reconcile, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(storage_service, "file_targets", _targets)
    monkeypatch.setattr(storage_service, "get", AsyncMock(return_value=b"data"))
    s3 = AsyncMock()
    monkeypatch.setattr(storage_service, "client", _client_factory(s3))

    res = await storage_reconcile.reconcile_once()

    assert res["done"] == 1 and res["failed"] == 0
    assert len(session.deleted) == 1          # запись снята из outbox
    s3.put_object.assert_awaited_once()
    assert session.committed is True


@pytest.mark.asyncio
async def test_put_row_source_missing_keeps_and_counts_failed(monkeypatch):
    row = _row(op="put", target="secondary")
    session = _FakeSession([row])
    monkeypatch.setattr(storage_reconcile, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(storage_service, "file_targets", _targets)
    monkeypatch.setattr(storage_service, "get", AsyncMock(return_value=None))  # источника нет
    monkeypatch.setattr(storage_service, "client", _client_factory(AsyncMock()))

    res = await storage_reconcile.reconcile_once()

    assert res["failed"] == 1 and res["done"] == 0
    assert session.deleted == []              # не снята — повторим позже
    assert row.attempts == 1


@pytest.mark.asyncio
async def test_delete_row(monkeypatch):
    session = _FakeSession([_row(op="delete", target="secondary")])
    monkeypatch.setattr(storage_reconcile, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(storage_service, "file_targets", _targets)
    s3 = AsyncMock()
    monkeypatch.setattr(storage_service, "client", _client_factory(s3))

    res = await storage_reconcile.reconcile_once()

    assert res["done"] == 1
    s3.delete_object.assert_awaited_once()
    assert len(session.deleted) == 1


@pytest.mark.asyncio
async def test_unknown_target_skipped_and_removed(monkeypatch):
    session = _FakeSession([_row(op="put", target="ghost")])
    monkeypatch.setattr(storage_reconcile, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(storage_service, "file_targets", _targets)
    monkeypatch.setattr(storage_service, "get", AsyncMock(return_value=b"x"))
    monkeypatch.setattr(storage_service, "client", _client_factory(AsyncMock()))

    res = await storage_reconcile.reconcile_once()

    assert res["skipped"] == 1
    assert len(session.deleted) == 1          # снята, т.к. таргета больше нет
