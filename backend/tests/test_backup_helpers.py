"""Юнит-тесты чистых хелперов backup_service."""

from datetime import datetime, timezone

from app.core import config
from app.services import backup_service


class TestParseDbUrl:
    def test_strips_asyncpg_and_parses(self, monkeypatch):
        monkeypatch.setattr(
            config.settings, "database_url",
            "postgresql+asyncpg://bob:secret@dbhost:6543/mydb",
        )
        d = backup_service._parse_db_url()
        assert d == {
            "host": "dbhost", "port": "6543", "user": "bob",
            "password": "secret", "dbname": "mydb",
        }

    def test_defaults_when_minimal(self, monkeypatch):
        monkeypatch.setattr(
            config.settings, "database_url",
            "postgresql://postgres@localhost/",
        )
        d = backup_service._parse_db_url()
        assert d["host"] == "localhost"
        assert d["port"] == "5432"
        assert d["user"] == "postgres"
        assert d["dbname"] == "postgres"


class TestBackupKey:
    def test_key_format(self, monkeypatch):
        monkeypatch.setattr(config.settings, "backup_s3_prefix", "db-backups/")
        now = datetime(2026, 7, 2, 15, 4, 5, tzinfo=timezone.utc)
        key = backup_service._backup_key(now)
        assert key == "db-backups/2026/07/dump_20260702_150405Z.dump"

    def test_prefix_without_slash_normalized(self, monkeypatch):
        monkeypatch.setattr(config.settings, "backup_s3_prefix", "dumps")
        now = datetime(2026, 1, 9, 1, 2, 3, tzinfo=timezone.utc)
        key = backup_service._backup_key(now)
        assert key.startswith("dumps/2026/01/dump_20260109_010203Z.dump")


class TestNormalizedPrefix:
    def test_adds_trailing_slash(self, monkeypatch):
        monkeypatch.setattr(config.settings, "backup_s3_prefix", "db-backups")
        assert backup_service._normalized_prefix() == "db-backups/"

    def test_keeps_existing_slash(self, monkeypatch):
        monkeypatch.setattr(config.settings, "backup_s3_prefix", "x/")
        assert backup_service._normalized_prefix() == "x/"


class TestIsBackupConfigured:
    def test_true_when_creds_and_bucket(self, monkeypatch):
        monkeypatch.setattr(config.settings, "backup_s3_endpoint_url", "https://storj")
        monkeypatch.setattr(config.settings, "backup_s3_access_key_id", "ak")
        monkeypatch.setattr(config.settings, "backup_s3_secret_access_key", "sk")
        monkeypatch.setattr(config.settings, "backup_s3_bucket", "ibra-db-backups")
        assert backup_service._is_backup_configured() is True

    def test_false_without_bucket(self, monkeypatch):
        monkeypatch.setattr(config.settings, "backup_s3_endpoint_url", "https://storj")
        monkeypatch.setattr(config.settings, "backup_s3_access_key_id", "ak")
        monkeypatch.setattr(config.settings, "backup_s3_secret_access_key", "sk")
        monkeypatch.setattr(config.settings, "backup_s3_bucket", "")
        assert backup_service._is_backup_configured() is False

    def test_falls_back_to_main_s3_creds(self, monkeypatch):
        # backup-креды пусты → _backup_creds берёт S3_*; при заданном bucket считается настроенным.
        monkeypatch.setattr(config.settings, "backup_s3_endpoint_url", "")
        monkeypatch.setattr(config.settings, "backup_s3_access_key_id", "")
        monkeypatch.setattr(config.settings, "backup_s3_secret_access_key", "")
        monkeypatch.setattr(config.settings, "s3_endpoint_url", "https://hostkey")
        monkeypatch.setattr(config.settings, "s3_access_key_id", "ak")
        monkeypatch.setattr(config.settings, "s3_secret_access_key", "sk")
        monkeypatch.setattr(config.settings, "backup_s3_bucket", "b")
        assert backup_service._is_backup_configured() is True
