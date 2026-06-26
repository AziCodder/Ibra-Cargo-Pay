from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.core import permissions


class TestPermissionsPure:
    def test_can_access_project_always_true_for_authenticated(self, admin_user, client_user):
        assert permissions.can_access_project(admin_user) is True
        assert permissions.can_access_project(client_user) is True

    def test_can_edit_project_admin_and_client(self, admin_user, client_user):
        assert permissions.can_edit_project(admin_user) is True
        assert permissions.can_edit_project(client_user) is True
        assert permissions.can_edit_project(SimpleNamespace(id=3, role="guest")) is False

    def test_can_edit_item_respects_shared_access(
        self, admin_user, client_user, item_shared, item_private
    ):
        assert permissions.can_edit_item(admin_user, item_private) is True
        assert permissions.can_edit_item(client_user, item_shared) is True
        assert permissions.can_edit_item(client_user, item_private) is False

    def test_can_view_item_cost_admin_only(self, admin_user, client_user):
        assert permissions.can_view_item_cost(admin_user) is True
        assert permissions.can_view_item_cost(client_user) is False

    def test_all_items_accessible(self, admin_user, client_user, item_shared, item_private):
        assert permissions.all_items_accessible(admin_user, [item_private]) is True
        assert permissions.all_items_accessible(client_user, [item_shared]) is True
        assert permissions.all_items_accessible(client_user, [item_shared, item_private]) is False
        assert permissions.all_items_accessible(client_user, []) is False

    def test_can_edit_payment_request(self, client_user, item_shared, item_private):
        assert permissions.can_edit_payment_request(client_user, [item_shared]) is True
        assert permissions.can_edit_payment_request(client_user, [item_private]) is False

    def test_can_delete_payment(self, client_user, item_shared):
        own = SimpleNamespace(created_by=client_user.id)
        foreign = SimpleNamespace(created_by=999)
        assert permissions.can_delete_payment(client_user, own, [item_shared]) is True
        assert permissions.can_delete_payment(client_user, foreign, [item_shared]) is False
        private = SimpleNamespace(shared_access=False, price=Decimal("1"))
        assert permissions.can_delete_payment(client_user, own, [private]) is False

    def test_default_shared_access_for_creator(self):
        assert permissions.default_shared_access_for_creator("client") is True
        assert permissions.default_shared_access_for_creator("admin") is False

    def test_effective_cost_price(self, item_shared, item_private):
        assert permissions.effective_cost_price(item_shared) == Decimal("80.00")
        assert permissions.effective_cost_price(item_private) == Decimal("100.00")


class TestEnsureProjectAccess:
    @pytest.mark.asyncio
    async def test_returns_project_when_exists(self, admin_user):
        project = SimpleNamespace(id=1, name="P1")
        db = AsyncMock()
        db.get = AsyncMock(return_value=project)

        result = await permissions.ensure_project_access(1, admin_user, db)

        assert result is project
        db.get.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_404_when_missing(self, client_user):
        db = AsyncMock()
        db.get = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc:
            await permissions.ensure_project_access(99, client_user, db)

        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_client_has_access_without_client_id_check(self, client_user):
        """После отвязки client_id любой авторизованный client видит проект."""
        project = SimpleNamespace(id=5, client_id=999)
        db = AsyncMock()
        db.get = AsyncMock(return_value=project)

        result = await permissions.ensure_project_access(5, client_user, db)

        assert result.client_id == 999


class TestModuleImport:
    def test_refactor_checklist_non_empty(self):
        assert len(permissions.REFACTOR_ACCESS_CHECKLIST) >= 5

    def test_module_imports_cleanly(self):
        assert callable(permissions.can_edit_item)
