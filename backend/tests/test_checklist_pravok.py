"""
Тесты чек-листа правок (telegra.ph/CHek-list-pravok-06-26).

Каждый тест проверяет конкретную строку чек-листа. Тесты не требуют БД:
они инспектируют схемы Pydantic, сигнатуры/зависимости роутов FastAPI,
чистые функции прав доступа и маркеры в исходниках фронтенда.

Нумерация классов и методов повторяет нумерацию разделов чек-листа.
"""

from __future__ import annotations

import inspect
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.api import (
    payment_request_attachments,
    payment_requests,
    payments,
    project_items,
    project_notes,
    projects,
)
from app.core import dependencies, permissions
from app.schemas.payment import PaymentUpdate
from app.schemas.payment_request import PaymentRequestListOut
from app.schemas.project import CurrencySummary, ProjectCreate, ProjectUpdate
from app.schemas.project_item import (
    ProjectItemAdminOut,
    ProjectItemClientOut,
    ProjectItemCreate,
)
from app.schemas.project_note import ProjectNoteCreate

FRONTEND_SRC = Path(__file__).resolve().parents[2] / "frontend" / "src"


# ── Вспомогательные функции инспекции ───────────────────────────────────────


def _dep_of(handler, param: str):
    """Вернуть callable из Depends(...) у параметра роута."""
    default = inspect.signature(handler).parameters[param].default
    return getattr(default, "dependency", None)


def _route_paths(router) -> list[str]:
    return [getattr(r, "path", "") for r in router.routes]


def _annotation_src(handler, param: str) -> str:
    return str(inspect.signature(handler).parameters[param].annotation)


def _read_front(rel: str) -> str:
    return (FRONTEND_SRC / rel).read_text(encoding="utf-8")


# ── 1. Проекты и клиенты ────────────────────────────────────────────────────


class Test01ProjectsAndClients:
    def test_create_has_no_client_selection(self):
        # «Отвязать проект от клиента — убрать выбор клиента»
        assert "client_id" not in ProjectCreate.model_fields
        assert "client_id" not in ProjectUpdate.model_fields

    def test_create_project_open_to_any_authenticated_user(self):
        # «Проекты общие — видны всем пользователям без ограничений»
        assert _dep_of(projects.create_project, "current_user") is dependencies.get_current_user
        assert _dep_of(projects.list_projects, "current_user") is dependencies.get_current_user

    def test_get_project_uses_unrestricted_access_gate(self):
        # Доступ к проекту через ensure_project_access (любая роль)
        src = inspect.getsource(projects.get_project)
        assert "ensure_project_access" in src

    def test_card_has_no_client_or_created_date(self):
        # «Из плитки убрать клиента и дату создания»
        card = _read_front("components/Projects/ProjectCard.tsx")
        assert "client" not in card.lower()
        assert "created_at" not in card  # дата создания не выводится

    def test_sort_by_name_and_created_at_both_directions(self):
        # «Сортировка: по алфавиту (туда/обратно) и по дате (туда/обратно)»
        ann_by = _annotation_src(projects.list_projects, "sort_by")
        ann_order = _annotation_src(projects.list_projects, "sort_order")
        assert "name" in ann_by and "created_at" in ann_by
        assert "asc" in ann_order and "desc" in ann_order

    def test_manual_drag_reorder_endpoint(self):
        # Ручной порядок проектов перетаскиванием (long-press)
        paths = _route_paths(projects.router)
        assert any(p.endswith("/projects/reorder") for p in paths)
        assert _dep_of(projects.reorder_projects, "current_user") is dependencies.get_current_user
        # режим manual поддержан в list_projects
        assert "manual" in _annotation_src(projects.list_projects, "sort_by")

    def test_sort_choice_persisted_in_storage(self):
        # «Выбор сохраняется и не сбрасывается при обновлении страницы»
        page = _read_front("pages/ProjectsPage.tsx")
        assert "readProjectSortFromStorage" in page
        assert "writeProjectSortToStorage" in page
        util = _read_front("utils/projectSort.ts")
        assert "localStorage" in util


# ── 2. Роль клиента — расширение прав + ограничения ──────────────────────────


class Test02ClientRole:
    def test_client_can_create_edit_delete_projects(self):
        assert permissions.can_edit_project(SimpleNamespace(id=2, role="client")) is True

    def test_client_can_add_nomenclature(self):
        # create_item открыт любому авторизованному (не require_admin)
        assert _dep_of(project_items.create_item, "current_user") is dependencies.get_current_user

    def test_shared_access_default_depends_on_creator_role(self):
        # «создал клиент → ВКЛ; создал админ → ВЫКЛ»
        assert permissions.default_shared_access_for_creator("client") is True
        assert permissions.default_shared_access_for_creator("admin") is False

    def test_closed_item_is_read_only_for_client(self):
        client = SimpleNamespace(id=2, role="client")
        shared = SimpleNamespace(shared_access=True, price=Decimal("1"))
        private = SimpleNamespace(shared_access=False, price=Decimal("1"))
        assert permissions.can_edit_item(client, shared) is True   # открыт → редактирует
        assert permissions.can_edit_item(client, private) is False  # закрыт → только смотрит

    def test_client_can_always_create_payment_request(self):
        # «Запросы на оплату клиент может добавлять ВСЕГДА»
        assert _dep_of(payment_requests.create_payment_request, "current_user") is dependencies.get_current_user

    def test_payment_delete_rules_open_vs_closed(self):
        # «по доступной — удалять; по закрытой — НЕ удалять»
        client = SimpleNamespace(id=2, role="client")
        own = SimpleNamespace(created_by=2)
        shared = SimpleNamespace(shared_access=True, price=Decimal("1"))
        private = SimpleNamespace(shared_access=False, price=Decimal("1"))
        assert permissions.can_delete_payment(client, own, [shared]) is True
        assert permissions.can_delete_payment(client, own, [private]) is False

    def test_client_never_sees_cost_price(self):
        # «Клиент никогда не видит строку себестоимости»
        assert "cost_price" not in ProjectItemClientOut.model_fields
        assert "cost_price" in ProjectItemAdminOut.model_fields
        assert permissions.can_view_item_cost(SimpleNamespace(role="client")) is False

    def test_client_sees_all_suppliers_brief(self):
        # «При создании проекта клиент видит всех поставщиков»
        from app.api import suppliers

        brief = next(r for r in suppliers.router.routes if getattr(r, "path", "").endswith("/brief"))
        assert _dep_of(brief.endpoint, "_user") is dependencies.get_current_user

    def test_client_has_no_access_to_db_users_and_supplier_mutations(self):
        # «Клиент не имеет доступа: к БД, пользователям, ролям, добавлению поставщиков»
        from app.api import suppliers, users

        # все мутации поставщиков (кроме /brief) — только админ
        for route in suppliers.router.routes:
            path = getattr(route, "path", "")
            methods = getattr(route, "methods", set())
            if path.endswith("/brief"):
                continue
            if methods & {"POST", "PUT", "DELETE"}:
                deps = [d.call for d in getattr(route, "dependant", SimpleNamespace(dependencies=[])).dependencies]
                # require_admin присутствует как Depends в сигнатуре
                params = inspect.signature(route.endpoint).parameters
                assert any(
                    getattr(p.default, "dependency", None) is dependencies.require_admin
                    for p in params.values()
                ), f"{path} {methods} должен требовать админа"
        # управление пользователями — только админ
        for route in users.router.routes:
            params = inspect.signature(route.endpoint).parameters
            assert any(
                getattr(p.default, "dependency", None) is dependencies.require_admin
                for p in params.values()
            ), f"users {route.path} должен требовать админа"


# ── 3. Себестоимость ────────────────────────────────────────────────────────


class Test03CostPrice:
    def test_cost_price_is_optional(self):
        # «Сделать опциональной»
        item = ProjectItemCreate(name="X", quantity=Decimal("1"), price=Decimal("10"), currency="USD")
        assert item.cost_price is None
        assert ProjectItemCreate.model_fields["cost_price"].is_required() is False

    def test_client_cost_equals_price(self):
        # «При добавлении товара клиентом себестоимость = цене товара»
        data = ProjectItemCreate(name="X", quantity=Decimal("1"), price=Decimal("55"), currency="USD")
        client = SimpleNamespace(role="client")
        admin = SimpleNamespace(role="admin")
        assert project_items._resolve_cost_price_on_create(client, data) == Decimal("55")
        assert project_items._resolve_cost_price_on_create(admin, data) is None  # админ задаёт сам

    def test_cost_hidden_from_client_schema(self):
        assert "cost_price" not in ProjectItemClientOut.model_fields


# ── 4. Оплаты / платежи ──────────────────────────────────────────────────────


class Test04Payments:
    def test_no_admin_confirmation(self):
        # «Убрать подтверждение оплаты от админа» — платёж сразу confirmed
        src = inspect.getsource(payments.add_payment)
        assert 'status="confirmed"' in src

    def test_no_confirm_or_reject_endpoints(self):
        paths = _route_paths(payments.router) + _route_paths(payments.router_project)
        assert not any("confirm" in p or "reject" in p for p in paths)

    def test_payment_date_is_editable(self):
        # «Возможность менять дату оплаты у уже загруженного платежа»
        assert "payment_date" in PaymentUpdate.model_fields
        assert any(
            getattr(r, "path", "").endswith("/{pay_id}") and "PATCH" in getattr(r, "methods", set())
            for r in payments.router.routes
        )

    def test_attachment_can_be_added_to_existing_request(self):
        # «Добавлять файлы к существующему запросу задним числом»
        assert _dep_of(payment_request_attachments.upload_attachment, "current_user") is dependencies.get_current_user
        front = _read_front("components/ProjectDetail/PaymentRequestDetailModal.tsx")
        assert "Добавить файл" in front and "uploadAttachment" in front

    def test_actually_paid_column_exists(self):
        # «Добавить столбец Фактически оплачено»
        assert "paid_amount" in PaymentRequestListOut.model_fields
        panel = _read_front("components/ProjectDetail/PaymentRequestsPanel.tsx")
        assert "Фактически оплачено" in panel

    def test_payment_date_rendered_white(self):
        # «Дату оплаты сделать белым цветом» (token.colorText в тёмной теме = светлый)
        front = _read_front("components/ProjectDetail/PaymentRequestDetailModal.tsx")
        assert "token.colorText" in front


# ── 5. Фильтры и сортировка заявок на оплату ──────────────────────────────────


class Test05PaymentRequestFilters:
    def test_sort_by_item_amount_date(self):
        # «Сортировка: по номенклатуре, по дате создания, по сумме»
        ann = _annotation_src(payment_requests.list_payment_requests, "sort_by")
        assert "created_at" in ann and "total_amount" in ann and "item_name" in ann

    def test_filter_by_nomenclature(self):
        # «Фильтр по номенклатуре»
        assert "item_ids" in inspect.signature(payment_requests.list_payment_requests).parameters

    def test_filters_by_date_and_status(self):
        # «Фильтры по дате и статусу»
        params = inspect.signature(payment_requests.list_payment_requests).parameters
        assert "date_from" in params and "date_to" in params
        assert "status_filter" in params

    def test_filter_bar_on_top_and_persisted(self):
        panel = _read_front("components/ProjectDetail/PaymentRequestsPanel.tsx")
        assert "readPaymentRequestFilters" in panel and "writePaymentRequestFilters" in panel


# ── 6. Номенклатура ──────────────────────────────────────────────────────────


class Test06Nomenclature:
    def test_sort_order_field_exists(self):
        from app.models.project_item import ProjectItem

        assert "sort_order" in ProjectItem.__table__.columns

    def test_manual_reorder_endpoint(self):
        # «Ручное упорядочивание номенклатуры внутри проекта» — bulk reorder
        paths = _route_paths(project_items.router)
        assert any(p.endswith("/reorder") for p in paths)
        # старые хрупкие swap-роуты удалены
        assert not any(p.endswith("/move-up") or p.endswith("/move-down") for p in paths)
        assert _dep_of(project_items.reorder_items, "current_user") is dependencies.get_current_user

    def test_reorder_available_to_any_user_with_project_access(self):
        # Порядок доступен любому (в т.ч. клиенту по закрытым позициям):
        # reorder_items не проверяет can_edit_item, только доступ к проекту.
        src = inspect.getsource(project_items.reorder_items)
        assert "can_edit_item" not in src
        assert "ensure_project_access" in src

    def test_list_ordered_by_sort_order(self):
        src = inspect.getsource(project_items.list_items)
        assert "sort_order" in src


# ── 7. Сводка / итоги ────────────────────────────────────────────────────────


class Test07Summary:
    def test_no_profit_in_summary_schema(self):
        # «Убрать подсчёт прибыли из итогов»
        assert "profit" not in CurrencySummary.model_fields

    def test_no_profit_in_summary_panel(self):
        panel = _read_front("components/ProjectDetail/ItemsPanel.tsx")
        assert "прибыл" not in panel.lower() and "profit" not in panel.lower()


# ── 8. Заметки по проекту ────────────────────────────────────────────────────


class Test08ProjectNotes:
    def test_note_visibility_private_or_shared(self):
        # «Реализовать заметки с частным/общим доступом»
        note = ProjectNoteCreate(content="hi")
        assert note.visibility == "private"
        assert "shared" in str(ProjectNoteCreate.model_fields["visibility"].annotation)

    def test_private_note_visible_only_to_author_or_admin(self):
        admin = SimpleNamespace(id=1, role="admin")
        author = SimpleNamespace(id=2, role="client")
        other = SimpleNamespace(id=3, role="client")
        private = SimpleNamespace(visibility="private", created_by=2)
        shared = SimpleNamespace(visibility="shared", created_by=2)
        assert project_notes._can_view_note(private, author) is True
        assert project_notes._can_view_note(private, admin) is True
        assert project_notes._can_view_note(private, other) is False
        assert project_notes._can_view_note(shared, other) is True

    def test_only_author_or_admin_can_edit_note(self):
        admin = SimpleNamespace(id=1, role="admin")
        author = SimpleNamespace(id=2, role="client")
        other = SimpleNamespace(id=3, role="client")
        note = SimpleNamespace(created_by=2)
        assert project_notes._can_edit_note(note, author) is True
        assert project_notes._can_edit_note(note, admin) is True
        assert project_notes._can_edit_note(note, other) is False

    def test_notes_panel_component_exists(self):
        assert (FRONTEND_SRC / "components/ProjectDetail/NotesPanel.tsx").exists()


# ── 9. Страница проекта ──────────────────────────────────────────────────────


class Test09ProjectPage:
    def test_default_tab_order_active_closed_all(self):
        # «По умолчанию В работе, затем Закрытые, затем Все»
        page = _read_front("pages/ProjectsPage.tsx")
        # порядок меток фильтра статусов соответствует порядку отображения
        assert page.index("В работе") < page.index("Закрытые") < page.index("Все")

    def test_default_status_is_active(self):
        page = _read_front("pages/ProjectsPage.tsx")
        assert "return 'active'" in page  # initialStatus() по умолчанию active
