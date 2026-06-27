"""Тесты payment_requests / payments / attachments (шаги 2.7–2.9)."""

from decimal import Decimal
from types import SimpleNamespace

from app.core import permissions
from app.schemas.payment_request import PaymentRequestListOut


class TestPaymentRequestPermissions:
    def test_client_can_always_create_conceptually(self):
        user = SimpleNamespace(id=2, role="client")
        assert permissions.can_access_project(user)

    def test_edit_request_requires_all_shared(self):
        user = SimpleNamespace(id=2, role="client")
        shared = SimpleNamespace(shared_access=True, price=Decimal("1"))
        private = SimpleNamespace(shared_access=False, price=Decimal("1"))
        assert permissions.can_edit_payment_request(user, [shared]) is True
        assert permissions.can_edit_payment_request(user, [shared, private]) is False

    def test_admin_can_edit_any_request(self):
        user = SimpleNamespace(id=1, role="admin")
        private = SimpleNamespace(shared_access=False, price=Decimal("1"))
        assert permissions.can_edit_payment_request(user, [private]) is True


class TestPaymentDeletePermissions:
    def test_client_delete_own_payment_with_shared_items(self):
        user = SimpleNamespace(id=2, role="client")
        payment = SimpleNamespace(created_by=2)
        items = [SimpleNamespace(shared_access=True, price=Decimal("10"))]
        assert permissions.can_delete_payment(user, payment, items) is True

    def test_client_cannot_delete_with_private_item(self):
        user = SimpleNamespace(id=2, role="client")
        payment = SimpleNamespace(created_by=2)
        items = [SimpleNamespace(shared_access=False, price=Decimal("10"))]
        assert permissions.can_delete_payment(user, payment, items) is False

    def test_client_cannot_delete_foreign_payment(self):
        user = SimpleNamespace(id=2, role="client")
        payment = SimpleNamespace(created_by=99)
        items = [SimpleNamespace(shared_access=True, price=Decimal("10"))]
        assert permissions.can_delete_payment(user, payment, items) is False

    def test_admin_deletes_any(self):
        user = SimpleNamespace(id=1, role="admin")
        payment = SimpleNamespace(created_by=99)
        items = [SimpleNamespace(shared_access=False, price=Decimal("1"))]
        assert permissions.can_delete_payment(user, payment, items) is True


class TestPaymentRequestListSchema:
    def test_list_out_has_paid_amount(self):
        assert "paid_amount" in PaymentRequestListOut.model_fields


class TestParseItemIds:
    def test_parse_item_ids(self):
        from app.api.payment_requests import _parse_item_ids

        assert _parse_item_ids(None) == []
        assert _parse_item_ids("") == []
        assert _parse_item_ids("1,2,3") == [1, 2, 3]
        assert _parse_item_ids("1, x, 3") == [1, 3]
