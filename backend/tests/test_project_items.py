"""Тесты раздела 2 backend: project_items (шаги 2.1–2.6)."""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.api import project_items as items_api
from app.core import permissions
from app.schemas.project_item import ProjectItemCreate, ProjectItemUpdate


class TestProjectItemSchemas:
    def test_create_cost_price_optional(self):
        data = ProjectItemCreate(
            name="Item",
            quantity=Decimal("1"),
            price=Decimal("100"),
            currency="CNY",
        )
        assert data.cost_price is None

    def test_update_has_shared_access(self):
        assert "shared_access" in ProjectItemUpdate.model_fields


class TestCreateItemDefaults:
    def test_client_cost_price_equals_price(self):
        user = SimpleNamespace(id=2, role="client")
        data = ProjectItemCreate(
            name="X",
            quantity=Decimal("2"),
            price=Decimal("50"),
            currency="USD",
        )
        assert items_api._resolve_cost_price_on_create(user, data) == Decimal("50")

    def test_admin_cost_price_from_request(self):
        user = SimpleNamespace(id=1, role="admin")
        data = ProjectItemCreate(
            name="X",
            quantity=Decimal("1"),
            price=Decimal("100"),
            cost_price=Decimal("80"),
            currency="CNY",
        )
        assert items_api._resolve_cost_price_on_create(user, data) == Decimal("80")

    def test_admin_cost_price_can_be_none(self):
        user = SimpleNamespace(id=1, role="admin")
        data = ProjectItemCreate(
            name="X",
            quantity=Decimal("1"),
            price=Decimal("100"),
            currency="CNY",
        )
        assert items_api._resolve_cost_price_on_create(user, data) is None

    def test_shared_access_defaults(self):
        assert permissions.default_shared_access_for_creator("client") is True
        assert permissions.default_shared_access_for_creator("admin") is False


class TestItemEditPermissions:
    def test_client_cannot_edit_private_item(self):
        user = SimpleNamespace(id=2, role="client")
        item = SimpleNamespace(shared_access=False, price=Decimal("1"))
        assert permissions.can_edit_item(user, item) is False

    def test_client_can_edit_shared_item(self):
        user = SimpleNamespace(id=2, role="client")
        item = SimpleNamespace(shared_access=True, price=Decimal("1"))
        assert permissions.can_edit_item(user, item) is True

    def test_admin_can_toggle_shared_access_in_schema(self):
        upd = ProjectItemUpdate(shared_access=False)
        assert upd.shared_access is False


class TestImportCostPrice:
    def test_cost_price_optional_in_excel(self):
        from app.services.import_service import _parse_decimal

        assert _parse_decimal(None, allow_none=True) is None
        assert _parse_decimal("", allow_none=True) is None
        assert _parse_decimal(80, allow_none=True) == Decimal("80")


class TestSortOrderHelper:
    @pytest.mark.asyncio
    async def test_next_sort_order_starts_at_zero(self):
        from unittest.mock import AsyncMock, MagicMock

        db = AsyncMock()
        result = MagicMock()
        result.scalar_one.return_value = -1
        db.execute = AsyncMock(return_value=result)

        n = await items_api._next_sort_order(1, db)
        assert n == 0

    @pytest.mark.asyncio
    async def test_next_sort_order_increments(self):
        from unittest.mock import AsyncMock, MagicMock

        db = AsyncMock()
        result = MagicMock()
        result.scalar_one.return_value = 5
        db.execute = AsyncMock(return_value=result)

        n = await items_api._next_sort_order(1, db)
        assert n == 6
