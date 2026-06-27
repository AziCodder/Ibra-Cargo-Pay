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


class TestProjectSummarySchema:
    def test_currency_summary_without_profit(self):
        from app.schemas.project import CurrencySummary

        assert "profit" not in CurrencySummary.model_fields
