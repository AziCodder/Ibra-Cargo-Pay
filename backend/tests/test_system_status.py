"""Юнит-тесты агрегатора статуса инфраструктуры (system_status)."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core import config
from app.services import storage_service, system_status
from app.services.system_status import ComponentStatus


def _t(name="primary"):
    return storage_service.S3Target(name, f"https://{name}", "ak", "sk", "r", "b")


def _client_factory(s3):
    @asynccontextmanager
    async def _factory(target, read_timeout: int = 15):
        yield s3

    return _factory


class _Row:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _FakeResult:
    def __init__(self, value=None, rows=None):
        self._value = value
        self._rows = rows or []

    def scalar_one(self):
        return self._value

    def one(self):
        return self._rows[0]

    def all(self):
        return self._rows


class _FakeDB:
    """Возвращает заготовленные результаты по порядку вызовов execute()."""

    def __init__(self, results):
        self._results = list(results)

    async def execute(self, *_a, **_kw):
        return self._results.pop(0)


class TestComponentStatus:
    def test_to_dict_without_latency(self):
        c = ComponentStatus("k", "Label", "ok", "detail")
        assert c.to_dict() == {"key": "k", "label": "Label", "status": "ok", "detail": "detail"}

    def test_to_dict_with_latency(self):
        c = ComponentStatus("k", "Label", "ok", "detail", latency_ms=42)
        assert c.to_dict()["latency_ms"] == 42


class TestCheckDatabase:
    @pytest.mark.asyncio
    async def test_primary_role(self):
        db = _FakeDB([_FakeResult(value=False)])
        c = await system_status._check_database(db)
        assert c.status == "ok"
        assert "primary" in c.detail

    @pytest.mark.asyncio
    async def test_standby_role(self):
        db = _FakeDB([_FakeResult(value=True)])
        c = await system_status._check_database(db)
        assert c.status == "ok"
        assert "standby" in c.detail

    @pytest.mark.asyncio
    async def test_down_on_exception(self):
        db = AsyncMock()
        db.execute.side_effect = RuntimeError("conn refused")
        c = await system_status._check_database(db)
        assert c.status == "down"


class TestCheckReplication:
    @pytest.mark.asyncio
    async def test_primary_no_replicas_degraded(self):
        db = _FakeDB([_FakeResult(rows=[])])
        c = await system_status._check_replication(db, "primary")
        assert c.status == "degraded"

    @pytest.mark.asyncio
    async def test_primary_with_replica_ok(self):
        row = _Row(client_addr="10.8.0.2", state="streaming", lag_bytes=0)
        db = _FakeDB([_FakeResult(rows=[row])])
        c = await system_status._check_replication(db, "primary")
        assert c.status == "ok"
        assert "10.8.0.2" in c.detail

    @pytest.mark.asyncio
    async def test_standby_fresh_lag_ok(self):
        db = _FakeDB([_FakeResult(rows=[_Row(age_sec=2)])])
        c = await system_status._check_replication(db, "standby")
        assert c.status == "ok"

    @pytest.mark.asyncio
    async def test_standby_stale_lag_degraded(self):
        db = _FakeDB([_FakeResult(rows=[_Row(age_sec=999)])])
        c = await system_status._check_replication(db, "standby")
        assert c.status == "degraded"

    @pytest.mark.asyncio
    async def test_standby_no_data_degraded(self):
        db = _FakeDB([_FakeResult(rows=[_Row(age_sec=None)])])
        c = await system_status._check_replication(db, "standby")
        assert c.status == "degraded"

    @pytest.mark.asyncio
    async def test_exception_down(self):
        db = AsyncMock()
        db.execute.side_effect = RuntimeError("x")
        c = await system_status._check_replication(db, "primary")
        assert c.status == "down"


class TestCheckS3Target:
    @pytest.mark.asyncio
    async def test_not_configured(self):
        c = await system_status._check_s3_target("k", "Label", None)
        assert c.status == "not_configured"

    @pytest.mark.asyncio
    async def test_ok(self, monkeypatch):
        s3 = AsyncMock()
        monkeypatch.setattr(storage_service, "client", _client_factory(s3))
        c = await system_status._check_s3_target("s3_primary", "S3 основной", _t("primary"))
        assert c.status == "ok"
        s3.head_bucket.assert_awaited_once_with(Bucket="b")

    @pytest.mark.asyncio
    async def test_down_on_failure(self, monkeypatch):
        s3 = AsyncMock()
        s3.head_bucket.side_effect = RuntimeError("no access")
        monkeypatch.setattr(storage_service, "client", _client_factory(s3))
        c = await system_status._check_s3_target("s3_primary", "S3 основной", _t("primary"))
        assert c.status == "down"


class TestCheckBackupTargets:
    @pytest.mark.asyncio
    async def test_none_configured(self, monkeypatch):
        from app.services import backup_service

        monkeypatch.setattr(backup_service, "_backup_targets", lambda: [])
        results = await system_status._check_backup_targets()
        assert len(results) == 1
        assert results[0].status == "not_configured"

    @pytest.mark.asyncio
    async def test_two_targets_checked(self, monkeypatch):
        from app.services import backup_service

        t1, t2 = _t("storj"), _t("main")
        monkeypatch.setattr(backup_service, "_backup_targets", lambda: [t1, t2])
        s3 = AsyncMock()
        monkeypatch.setattr(storage_service, "client", _client_factory(s3))
        results = await system_status._check_backup_targets()
        assert len(results) == 2
        assert all(r.status == "ok" for r in results)


class TestStorageOutbox:
    @pytest.mark.asyncio
    async def test_empty_ok(self):
        db = _FakeDB([_FakeResult(value=0)])
        c = await system_status._check_storage_outbox(db)
        assert c.status == "ok"

    @pytest.mark.asyncio
    async def test_pending_degraded(self):
        db = _FakeDB([_FakeResult(value=3)])
        c = await system_status._check_storage_outbox(db)
        assert c.status == "degraded"
        assert "3" in c.detail


class TestSelfAndPeerVps:
    def test_self_primary_label(self):
        c = system_status._self_vps_status("primary")
        assert c.label == "VPS основной"
        assert c.status == "ok"

    def test_self_standby_label(self):
        c = system_status._self_vps_status("standby")
        assert c.label == "VPS резервный"

    @pytest.mark.asyncio
    async def test_peer_not_configured(self, monkeypatch):
        monkeypatch.setattr(config.settings, "standby_wg_ip", "")
        c = await system_status._check_peer_vps("primary")
        assert c.status == "not_configured"

    @pytest.mark.asyncio
    async def test_peer_ok(self, monkeypatch):
        monkeypatch.setattr(config.settings, "standby_wg_ip", "10.8.0.2")

        class _Resp:
            status_code = 200

        class _FakeHttpxClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, _url):
                return _Resp()

        import httpx

        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: _FakeHttpxClient())
        c = await system_status._check_peer_vps("primary")
        assert c.status == "ok"
        assert c.label == "VPS резервный"

    @pytest.mark.asyncio
    async def test_peer_down_on_exception(self, monkeypatch):
        monkeypatch.setattr(config.settings, "standby_wg_ip", "10.8.0.2")

        class _FailingClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, _url):
                raise RuntimeError("timeout")

        import httpx

        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: _FailingClient())
        c = await system_status._check_peer_vps("primary")
        assert c.status == "down"


class TestOverall:
    def test_all_ok(self):
        cs = [ComponentStatus("a", "A", "ok"), ComponentStatus("b", "B", "ok")]
        assert system_status._overall(cs) == "ok"

    def test_degraded_wins_over_ok(self):
        cs = [ComponentStatus("a", "A", "ok"), ComponentStatus("b", "B", "degraded")]
        assert system_status._overall(cs) == "degraded"

    def test_down_wins_over_degraded(self):
        cs = [ComponentStatus("a", "A", "degraded"), ComponentStatus("b", "B", "down")]
        assert system_status._overall(cs) == "down"

    def test_not_configured_does_not_affect_overall(self):
        cs = [ComponentStatus("a", "A", "ok"), ComponentStatus("b", "B", "not_configured")]
        assert system_status._overall(cs) == "ok"
