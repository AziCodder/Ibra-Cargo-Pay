"""Тесты раздела 8: project_notes (шаги 8.3–8.4)."""

from datetime import datetime, timezone
from types import SimpleNamespace

from app.api import project_notes as notes_api
from app.schemas.project_note import ProjectNoteCreate, ProjectNoteUpdate


class TestProjectNoteSchemas:
    def test_create_defaults_private(self):
        data = ProjectNoteCreate(content="Hello")
        assert data.visibility == "private"

    def test_update_partial(self):
        upd = ProjectNoteUpdate(visibility="shared")
        assert upd.content is None
        assert upd.visibility == "shared"


class TestNotePermissions:
    def _note(self, **kwargs):
        defaults = {
            "id": 1,
            "visibility": "private",
            "created_by": 2,
            "author": SimpleNamespace(full_name="Author"),
            "project_id": 1,
            "content": "text",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    def test_shared_note_visible_to_all(self):
        note = self._note(visibility="shared")
        client = SimpleNamespace(id=99, role="client")
        assert notes_api._can_view_note(note, client) is True

    def test_private_note_visible_to_author(self):
        note = self._note(visibility="private", created_by=2)
        author = SimpleNamespace(id=2, role="client")
        assert notes_api._can_view_note(note, author) is True

    def test_private_note_visible_to_admin(self):
        note = self._note(visibility="private", created_by=2)
        admin = SimpleNamespace(id=1, role="admin")
        assert notes_api._can_view_note(note, admin) is True

    def test_private_note_hidden_from_other_client(self):
        note = self._note(visibility="private", created_by=2)
        other = SimpleNamespace(id=99, role="client")
        assert notes_api._can_view_note(note, other) is False

    def test_edit_only_author_or_admin(self):
        note = self._note(created_by=2)
        author = SimpleNamespace(id=2, role="client")
        admin = SimpleNamespace(id=1, role="admin")
        other = SimpleNamespace(id=99, role="client")
        assert notes_api._can_edit_note(note, author) is True
        assert notes_api._can_edit_note(note, admin) is True
        assert notes_api._can_edit_note(note, other) is False

    def test_note_out_includes_can_edit(self):
        note = self._note(created_by=2)
        admin = SimpleNamespace(id=1, role="admin")
        out = notes_api._note_out(note, admin)
        assert out.author_name == "Author"
        assert out.can_edit is True
