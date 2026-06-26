"""Тесты раздела 1 backend: проекты без client_id."""

import pytest
from pydantic import ValidationError

from app.schemas.project import ProjectCreate, ProjectOut, ProjectUpdate


class TestProjectSchemas:
    def test_create_without_client_id(self):
        data = ProjectCreate(name="Новый проект", description="desc")
        assert data.name == "Новый проект"
        assert "client_id" not in ProjectCreate.model_fields

    def test_update_without_client_id(self):
        data = ProjectUpdate(name="Renamed")
        assert "client_id" not in ProjectUpdate.model_fields

    def test_out_allows_null_client(self):
        from datetime import datetime, timezone

        out = ProjectOut(
            id=1,
            project_number=100,
            name="P",
            client_id=None,
            client=None,
            status="active",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        assert out.client_id is None
        assert out.client is None


class TestCreatorChatId:
    @pytest.mark.asyncio
    async def test_returns_telegram_from_payment_creator(self):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock

        from app.api.payments import _get_creator_chat_id

        user = SimpleNamespace(telegram_chat_id=12345)
        db = AsyncMock()
        db.get = AsyncMock(return_value=user)

        chat_id = await _get_creator_chat_id(7, db)

        assert chat_id == 12345
        db.get.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_none_when_user_missing(self):
        from unittest.mock import AsyncMock

        from app.api.payments import _get_creator_chat_id

        db = AsyncMock()
        db.get = AsyncMock(return_value=None)

        assert await _get_creator_chat_id(99, db) is None
