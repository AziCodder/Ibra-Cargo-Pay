"""Юнит-тесты dual-target логики backup_service (дампы БД в два хранилища)."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

from app.core import config
from app.services import backup_service, storage_service


def _set(monkeypatch, **kw):
    for k, v in kw.items():
        monkeypatch.setattr(config.settings, k, v)


def _client_factory(s3_by_name: dict):
    @asynccontextmanager
    async def _factory(target, read_timeout: int = 15):
        yield s3_by_name[target.name]

    return _factory


class _FakeBody:
    def __init__(self, data):
        self._data = data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def read(self):
        return self._data


# ─── _backup_targets ─────────────────────────────────────────────────────────

class TestBackupTargets:
    def test_two_distinct_providers(self, monkeypatch):
        _set(monkeypatch,
             backup_s3_endpoint_url="https://storj", backup_s3_access_key_id="ak",
             backup_s3_secret_access_key="sk", backup_s3_region="us-1",
             backup_s3_bucket="ibra-db-backups",
             s3_endpoint_url="https://hostkey", s3_access_key_id="ak2",
             s3_secret_access_key="sk2", s3_region="nl", s3_bucket_name="files")
        targets = backup_service._backup_targets()
        assert [t.name for t in targets] == ["storj", "main"]
        assert targets[0].bucket == "ibra-db-backups"
        assert targets[1].bucket == "files"

    def test_dedup_same_endpoint_and_bucket(self, monkeypatch):
        # backup-креды пусты → fallback на s3_*; backup-бакет == основному → дубль отсекается.
        _set(monkeypatch,
             backup_s3_endpoint_url="", backup_s3_access_key_id="",
             backup_s3_secret_access_key="", backup_s3_region="",
             backup_s3_bucket="files",
             s3_endpoint_url="https://hostkey", s3_access_key_id="ak",
             s3_secret_access_key="sk", s3_region="nl", s3_bucket_name="files")
        targets = backup_service._backup_targets()
        assert len(targets) == 1

    def test_only_main_when_no_backup_bucket(self, monkeypatch):
        _set(monkeypatch,
             backup_s3_endpoint_url="", backup_s3_access_key_id="",
             backup_s3_secret_access_key="", backup_s3_region="", backup_s3_bucket="",
             s3_endpoint_url="https://hostkey", s3_access_key_id="ak",
             s3_secret_access_key="sk", s3_region="nl", s3_bucket_name="files")
        targets = backup_service._backup_targets()
        assert [t.name for t in targets] == ["main"]


# ─── _upload (дамп в оба) ────────────────────────────────────────────────────

class TestUpload:
    @pytest.mark.asyncio
    async def test_uploads_to_all_targets(self, monkeypatch):
        t1 = storage_service.S3Target("storj", "e1", "a", "s", "r", "b1")
        t2 = storage_service.S3Target("main", "e2", "a", "s", "r", "b2")
        s3a, s3b = AsyncMock(), AsyncMock()
        monkeypatch.setattr(backup_service, "_backup_targets", lambda: [t1, t2])
        monkeypatch.setattr(storage_service, "client", _client_factory({"storj": s3a, "main": s3b}))

        await backup_service._upload("db-backups/x.dump", b"DUMP")
        s3a.put_object.assert_awaited_once()
        s3b.put_object.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_all_fail_raises(self, monkeypatch):
        t1 = storage_service.S3Target("storj", "e1", "a", "s", "r", "b1")
        s3a = AsyncMock()
        s3a.put_object.side_effect = RuntimeError("down")
        monkeypatch.setattr(backup_service, "_backup_targets", lambda: [t1])
        monkeypatch.setattr(storage_service, "client", _client_factory({"storj": s3a}))

        with pytest.raises(backup_service.BackupExecutionError):
            await backup_service._upload("k", b"d")

    @pytest.mark.asyncio
    async def test_partial_failure_still_ok(self, monkeypatch):
        t1 = storage_service.S3Target("storj", "e1", "a", "s", "r", "b1")
        t2 = storage_service.S3Target("main", "e2", "a", "s", "r", "b2")
        s3a = AsyncMock()
        s3b = AsyncMock()
        s3b.put_object.side_effect = RuntimeError("main down")
        monkeypatch.setattr(backup_service, "_backup_targets", lambda: [t1, t2])
        monkeypatch.setattr(storage_service, "client", _client_factory({"storj": s3a, "main": s3b}))

        await backup_service._upload("k", b"d")  # storj принял — не бросаем
        s3a.put_object.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_targets_raises(self, monkeypatch):
        monkeypatch.setattr(backup_service, "_backup_targets", lambda: [])
        with pytest.raises(backup_service.BackupExecutionError):
            await backup_service._upload("k", b"d")


# ─── _download_dump (fallback между таргетами) ───────────────────────────────

class TestDownloadDump:
    @pytest.mark.asyncio
    async def test_falls_back_when_missing_in_first(self, monkeypatch):
        from botocore.exceptions import ClientError

        t1 = storage_service.S3Target("storj", "e1", "a", "s", "r", "b1")
        t2 = storage_service.S3Target("main", "e2", "a", "s", "r", "b2")
        s3a = AsyncMock()
        s3a.get_object.side_effect = ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        s3b = AsyncMock()
        s3b.get_object.return_value = {"Body": _FakeBody(b"DUMP")}
        monkeypatch.setattr(backup_service, "_backup_targets", lambda: [t1, t2])
        monkeypatch.setattr(storage_service, "client", _client_factory({"storj": s3a, "main": s3b}))

        assert await backup_service._download_dump("db-backups/x.dump") == b"DUMP"

    @pytest.mark.asyncio
    async def test_not_found_anywhere_raises_notfound(self, monkeypatch):
        from botocore.exceptions import ClientError

        t1 = storage_service.S3Target("storj", "e1", "a", "s", "r", "b1")
        s3a = AsyncMock()
        s3a.get_object.side_effect = ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        monkeypatch.setattr(backup_service, "_backup_targets", lambda: [t1])
        monkeypatch.setattr(storage_service, "client", _client_factory({"storj": s3a}))

        with pytest.raises(backup_service.BackupNotFoundError):
            await backup_service._download_dump("k")

    @pytest.mark.asyncio
    async def test_other_error_raises_execution(self, monkeypatch):
        t1 = storage_service.S3Target("storj", "e1", "a", "s", "r", "b1")
        s3a = AsyncMock()
        s3a.get_object.side_effect = RuntimeError("network")
        monkeypatch.setattr(backup_service, "_backup_targets", lambda: [t1])
        monkeypatch.setattr(storage_service, "client", _client_factory({"storj": s3a}))

        with pytest.raises(backup_service.BackupExecutionError):
            await backup_service._download_dump("k")
