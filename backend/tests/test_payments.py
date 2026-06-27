"""Тесты раздела 4 backend: payments (шаги 4.1–4.3)."""

from datetime import date

from app.schemas.payment import PaymentOut, PaymentUpdate


class TestPaymentSchemas:
    def test_out_defaults_to_confirmed(self):
        assert PaymentOut.model_fields["status"].default == "confirmed"

    def test_payment_update_accepts_null_date(self):
        data = PaymentUpdate(payment_date=None)
        assert data.payment_date is None

    def test_payment_update_accepts_date(self):
        data = PaymentUpdate(payment_date=date(2025, 1, 15))
        assert data.payment_date == date(2025, 1, 15)
