"""Юнит-тесты dual-write слоя storage_service."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services import storage_service
from app.services.storage_service import S3Target


# ─── helpers ────────────────────────────────────────────────────────────────

def _target(name: str, bucket: str = "b") -> S3Target:
    return S3Target(
        name=name,
        endpoint_url=f"https://{name}.example",
        access_key_id="ak",
        secret_access_key="sk",
        region="r",
        bucket=bucket,
    )


class _FakeBody:
    def __init__(self, data: bytes):
        self._data = data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def read(self) -> bytes:
        return self._data


def _client_factory(s3_by_name: dict):
    """Возвращает подмену storage_service.client → async-cm, отдающий нужный s3-мок."""

    @asynccontextmanager
    async def _factory(target, read_timeout: int = 15):
        yield s3_by_name[target.name]

    return _factory


# ─── S3Target / выбор таргетов ───────────────────────────────────────────────

class TestTargets:
    def test_configured_true_when_all_fields(self):
        assert _target("primary").configured is True

    def test_configured_false_when_missing_field(self):
        assert S3Target("x", "", "ak", "sk", "r", "b").configured is False
        assert S3Target("x", "e", "ak", "sk", "r", "").configured is False

    def test_file_targets_primary_only(self, monkeypatch):
        from app.core import config
        monkeypatch.setattr(config.settings, "s3_endpoint_url", "https://p")
        monkeypatch.setattr(config.settings, "s3_access_key_id", "ak")
        monkeypatch.setattr(config.settings, "s3_secret_access_key", "sk")
        monkeypatch.setattr(config.settings, "s3_bucket_name", "files")
        monkeypatch.setattr(config.settings, "s3_secondary_endpoint_url", "")
        monkeypatch.setattr(config.settings, "s3_secondary_access_key_id", "")
        monkeypatch.setattr(config.settings, "s3_secondary_secret_access_key", "")

        targets = storage_service.file_targets()
        assert [t.name for t in targets] == ["primary"]

    def test_file_targets_both(self, monkeypatch):
        from app.core import config
        for k, v in {
            "s3_endpoint_url": "https://p", "s3_access_key_id": "ak",
            "s3_secret_access_key": "sk", "s3_bucket_name": "files",
            "s3_secondary_endpoint_url": "https://s", "s3_secondary_access_key_id": "ak2",
            "s3_secondary_secret_access_key": "sk2", "s3_secondary_bucket": "files2",
            "s3_secondary_region": "us-1",
        }.items():
            monkeypatch.setattr(config.settings, k, v)

        targets = storage_service.file_targets()
        assert [t.name for t in targets] == ["primary", "secondary"]
        assert targets[1].bucket == "files2"

    def test_file_targets_secondary_bucket_defaults_to_primary(self, monkeypatch):
        from app.core import config
        for k, v in {
            "s3_endpoint_url": "https://p", "s3_access_key_id": "ak",
            "s3_secret_access_key": "sk", "s3_bucket_name": "files",
            "s3_secondary_endpoint_url": "https://s", "s3_secondary_access_key_id": "ak2",
            "s3_secondary_secret_access_key": "sk2", "s3_secondary_bucket": "",
        }.items():
            monkeypatch.setattr(config.settings, k, v)
        targets = storage_service.file_targets()
        assert targets[1].bucket == "files"

    def test_file_targets_none_when_unconfigured(self, monkeypatch):
        from app.core import config
        for k in ("s3_endpoint_url", "s3_access_key_id", "s3_secret_access_key",
                  "s3_secondary_endpoint_url", "s3_secondary_access_key_id",
                  "s3_secondary_secret_access_key"):
            monkeypatch.setattr(config.settings, k, "")
        assert storage_service.file_targets() == []

    def test_target_by_name(self):
        ts = [_target("primary"), _target("secondary")]
        assert storage_service.target_by_name("secondary", ts).name == "secondary"
        assert storage_service.target_by_name("nope", ts) is None

    def test_client_config_signature_and_pathstyle(self):
        cfg = storage_service._client_config()
        assert cfg.signature_version == "s3v4"
        assert cfg.s3["addressing_style"] == "path"


# ─── put ─────────────────────────────────────────────────────────────────────

class TestPut:
    @pytest.mark.asyncio
    async def test_writes_to_all_targets(self, monkeypatch):
        t1, t2 = _target("primary"), _target("secondary")
        s3a, s3b = AsyncMock(), AsyncMock()
        monkeypatch.setattr(storage_service, "file_targets", lambda: [t1, t2])
        monkeypatch.setattr(storage_service, "client", _client_factory({"primary": s3a, "secondary": s3b}))
        enq = AsyncMock()
        monkeypatch.setattr(storage_service, "_enqueue_outbox", enq)

        await storage_service.put("k", b"data", content_type="text/plain")

        s3a.put_object.assert_awaited_once()
        s3b.put_object.assert_awaited_once()
        assert s3a.put_object.await_args.kwargs["ContentType"] == "text/plain"
        enq.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_one_target_fails_still_ok_and_enqueues(self, monkeypatch):
        t1, t2 = _target("primary"), _target("secondary")
        s3a = AsyncMock()
        s3b = AsyncMock()
        s3b.put_object.side_effect = RuntimeError("down")
        monkeypatch.setattr(storage_service, "file_targets", lambda: [t1, t2])
        monkeypatch.setattr(storage_service, "client", _client_factory({"primary": s3a, "secondary": s3b}))
        enq = AsyncMock()
        monkeypatch.setattr(storage_service, "_enqueue_outbox", enq)

        await storage_service.put("k", b"d")  # не бросает — один таргет принял

        enq.assert_awaited_once()
        assert enq.await_args.args[:3] == ("k", "put", "secondary")

    @pytest.mark.asyncio
    async def test_all_fail_raises(self, monkeypatch):
        t1 = _target("primary")
        s3a = AsyncMock()
        s3a.put_object.side_effect = RuntimeError("down")
        monkeypatch.setattr(storage_service, "file_targets", lambda: [t1])
        monkeypatch.setattr(storage_service, "client", _client_factory({"primary": s3a}))
        monkeypatch.setattr(storage_service, "_enqueue_outbox", AsyncMock())

        with pytest.raises(RuntimeError):
            await storage_service.put("k", b"d")

    @pytest.mark.asyncio
    async def test_no_targets_raises(self, monkeypatch):
        monkeypatch.setattr(storage_service, "file_targets", lambda: [])
        with pytest.raises(RuntimeError):
            await storage_service.put("k", b"d")


# ─── delete ──────────────────────────────────────────────────────────────────

class TestDelete:
    @pytest.mark.asyncio
    async def test_deletes_from_all(self, monkeypatch):
        t1, t2 = _target("primary"), _target("secondary")
        s3a, s3b = AsyncMock(), AsyncMock()
        monkeypatch.setattr(storage_service, "file_targets", lambda: [t1, t2])
        monkeypatch.setattr(storage_service, "client", _client_factory({"primary": s3a, "secondary": s3b}))
        monkeypatch.setattr(storage_service, "_enqueue_outbox", AsyncMock())

        await storage_service.delete("k")
        s3a.delete_object.assert_awaited_once()
        s3b.delete_object.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_failure_enqueues_no_raise(self, monkeypatch):
        t1 = _target("primary")
        s3a = AsyncMock()
        s3a.delete_object.side_effect = RuntimeError("x")
        monkeypatch.setattr(storage_service, "file_targets", lambda: [t1])
        monkeypatch.setattr(storage_service, "client", _client_factory({"primary": s3a}))
        enq = AsyncMock()
        monkeypatch.setattr(storage_service, "_enqueue_outbox", enq)

        await storage_service.delete("k")  # best-effort, без исключения
        enq.assert_awaited_once()
        assert enq.await_args.args[:3] == ("k", "delete", "primary")

    @pytest.mark.asyncio
    async def test_no_targets_noop(self, monkeypatch):
        monkeypatch.setattr(storage_service, "file_targets", lambda: [])
        await storage_service.delete("k")  # просто не падает


# ─── get / presigned ─────────────────────────────────────────────────────────

class TestGet:
    @pytest.mark.asyncio
    async def test_returns_from_first(self, monkeypatch):
        t1, t2 = _target("primary"), _target("secondary")
        s3a = AsyncMock()
        s3a.get_object.return_value = {"Body": _FakeBody(b"hello")}
        monkeypatch.setattr(storage_service, "file_targets", lambda: [t1, t2])
        monkeypatch.setattr(storage_service, "client", _client_factory({"primary": s3a, "secondary": AsyncMock()}))

        assert await storage_service.get("k") == b"hello"

    @pytest.mark.asyncio
    async def test_falls_back_to_second(self, monkeypatch):
        t1, t2 = _target("primary"), _target("secondary")
        s3a = AsyncMock()
        s3a.get_object.side_effect = RuntimeError("primary down")
        s3b = AsyncMock()
        s3b.get_object.return_value = {"Body": _FakeBody(b"backup")}
        monkeypatch.setattr(storage_service, "file_targets", lambda: [t1, t2])
        monkeypatch.setattr(storage_service, "client", _client_factory({"primary": s3a, "secondary": s3b}))

        assert await storage_service.get("k") == b"backup"

    @pytest.mark.asyncio
    async def test_none_when_all_fail(self, monkeypatch):
        t1 = _target("primary")
        s3a = AsyncMock()
        s3a.get_object.side_effect = RuntimeError("x")
        monkeypatch.setattr(storage_service, "file_targets", lambda: [t1])
        monkeypatch.setattr(storage_service, "client", _client_factory({"primary": s3a}))
        assert await storage_service.get("k") is None


class TestPresigned:
    @pytest.mark.asyncio
    async def test_returns_url_from_first(self, monkeypatch):
        t1 = _target("primary")
        s3a = AsyncMock()
        s3a.generate_presigned_url.return_value = "http://url/k"
        monkeypatch.setattr(storage_service, "file_targets", lambda: [t1])
        monkeypatch.setattr(storage_service, "client", _client_factory({"primary": s3a}))
        assert await storage_service.presigned("k") == "http://url/k"

    @pytest.mark.asyncio
    async def test_none_when_all_fail(self, monkeypatch):
        t1 = _target("primary")
        s3a = AsyncMock()
        s3a.generate_presigned_url.side_effect = RuntimeError("x")
        monkeypatch.setattr(storage_service, "file_targets", lambda: [t1])
        monkeypatch.setattr(storage_service, "client", _client_factory({"primary": s3a}))
        assert await storage_service.presigned("k") is None
