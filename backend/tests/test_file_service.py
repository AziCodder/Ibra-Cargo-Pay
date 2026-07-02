"""Юнит-тесты file_service (тонкие обёртки над storage_service)."""

from unittest.mock import AsyncMock

import pytest

from app.services import file_service, storage_service
from app.services.storage_service import S3Target


def _t():
    return S3Target("primary", "https://p", "ak", "sk", "r", "b")


class TestPureHelpers:
    def test_sanitize_strips_path_and_bad_chars(self):
        assert file_service.sanitize_filename("../../etc/pa ss!@#.pdf") == "pa ss___.pdf"
        assert file_service.sanitize_filename("") == "file"

    def test_validate_extension_ok(self):
        for name in ("a.pdf", "b.PNG", "c.xlsx", "d.jpeg"):
            file_service.validate_file_extension(name)  # не бросает

    def test_validate_extension_rejects(self):
        with pytest.raises(ValueError):
            file_service.validate_file_extension("evil.exe")

    def test_is_s3_configured(self, monkeypatch):
        monkeypatch.setattr(storage_service, "file_targets", lambda: [_t()])
        assert file_service._is_s3_configured() is True
        monkeypatch.setattr(storage_service, "file_targets", lambda: [])
        assert file_service._is_s3_configured() is False


class TestUpload:
    @pytest.mark.asyncio
    async def test_stub_key_when_unconfigured(self, monkeypatch):
        monkeypatch.setattr(storage_service, "file_targets", lambda: [])
        put = AsyncMock()
        monkeypatch.setattr(storage_service, "put", put)

        key = await file_service.upload_file(b"x", "report.pdf", prefix="uploads")
        assert key.startswith("uploads/") and key.endswith(".pdf")
        put.assert_not_awaited()  # ничего не залито

    @pytest.mark.asyncio
    async def test_uploads_and_returns_key(self, monkeypatch):
        monkeypatch.setattr(storage_service, "file_targets", lambda: [_t()])
        put = AsyncMock()
        monkeypatch.setattr(storage_service, "put", put)

        key = await file_service.upload_file(b"data", "Photo.PNG", prefix="suppliers")
        assert key.startswith("suppliers/") and key.endswith(".png")
        put.assert_awaited_once()
        assert put.await_args.args[0] == key
        assert put.await_args.args[1] == b"data"


class TestDelegation:
    @pytest.mark.asyncio
    async def test_delete_delegates(self, monkeypatch):
        monkeypatch.setattr(storage_service, "file_targets", lambda: [_t()])
        d = AsyncMock()
        monkeypatch.setattr(storage_service, "delete", d)
        await file_service.delete_file("k")
        d.assert_awaited_once_with("k")

    @pytest.mark.asyncio
    async def test_delete_noop_when_unconfigured(self, monkeypatch):
        monkeypatch.setattr(storage_service, "file_targets", lambda: [])
        d = AsyncMock()
        monkeypatch.setattr(storage_service, "delete", d)
        await file_service.delete_file("k")
        d.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_download_delegates(self, monkeypatch):
        monkeypatch.setattr(storage_service, "file_targets", lambda: [_t()])
        g = AsyncMock(return_value=b"bytes")
        monkeypatch.setattr(storage_service, "get", g)
        assert await file_service.download_file_bytes("k") == b"bytes"

    @pytest.mark.asyncio
    async def test_download_none_when_unconfigured(self, monkeypatch):
        monkeypatch.setattr(storage_service, "file_targets", lambda: [])
        assert await file_service.download_file_bytes("k") is None

    @pytest.mark.asyncio
    async def test_presigned_delegates(self, monkeypatch):
        monkeypatch.setattr(storage_service, "file_targets", lambda: [_t()])
        p = AsyncMock(return_value="http://u")
        monkeypatch.setattr(storage_service, "presigned", p)
        assert await file_service.get_presigned_url("k", expires_in=60) == "http://u"
        p.assert_awaited_once_with("k", expires_in=60)

    @pytest.mark.asyncio
    async def test_presigned_none_when_unconfigured(self, monkeypatch):
        monkeypatch.setattr(storage_service, "file_targets", lambda: [])
        assert await file_service.get_presigned_url("k") is None
