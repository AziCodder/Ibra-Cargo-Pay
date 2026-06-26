import pytest


@pytest.fixture
def admin_user():
    from types import SimpleNamespace

    return SimpleNamespace(id=1, role="admin")


@pytest.fixture
def client_user():
    from types import SimpleNamespace

    return SimpleNamespace(id=2, role="client")


@pytest.fixture
def item_shared():
    from decimal import Decimal
    from types import SimpleNamespace

    return SimpleNamespace(
        shared_access=True,
        price=Decimal("100.00"),
        cost_price=Decimal("80.00"),
    )


@pytest.fixture
def item_private():
    from decimal import Decimal
    from types import SimpleNamespace

    return SimpleNamespace(
        shared_access=False,
        price=Decimal("100.00"),
        cost_price=None,
    )
