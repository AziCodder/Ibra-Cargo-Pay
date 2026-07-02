"""
Проверка связки с backup-хранилищем (Storj/S3): put → list → delete.

Использует те же креды и настройки, что и рабочий backup_service
(BACKUP_S3_* из .env, fallback на S3_*). Ничего в бакете не оставляет.

Запуск ВНУТРИ backend-контейнера (там уже есть зависимости и .env):
    docker compose exec backend python scripts/test_backup_s3.py

Либо локально, если установлены aioboto3/botocore и заполнен .env.
"""

import asyncio
import sys
from datetime import datetime, timezone

from app.services import backup_service


async def main() -> int:
    if not backup_service._is_backup_configured():
        print("❌ Бэкапы не настроены: проверь BACKUP_S3_* (или S3_*) в .env")
        return 1

    creds = backup_service._backup_creds()
    bucket = backup_service.settings.backup_s3_bucket
    prefix = backup_service._normalized_prefix()
    key = f"{prefix}_selftest_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}.txt"
    body = b"storj backup self-test — safe to delete"

    print(f"→ endpoint : {creds['endpoint_url']}")
    print(f"→ bucket   : {bucket}")
    print(f"→ test key : {key}")
    print("-" * 50)

    session = backup_service._s3_session()
    kwargs = backup_service._s3_client_kwargs()

    async with session.client("s3", **kwargs) as s3:
        # 1. PUT
        await s3.put_object(Bucket=bucket, Key=key, Body=body)
        print("✅ put_object   — запись прошла")

        # 2. LIST (проверяем, что объект виден)
        resp = await s3.list_objects_v2(Bucket=bucket, Prefix=key)
        found = any(o["Key"] == key for o in resp.get("Contents", []))
        print(f"✅ list_objects — объект {'виден' if found else 'НЕ виден'}")

        # 3. GET (проверяем целостность)
        got = await s3.get_object(Bucket=bucket, Key=key)
        async with got["Body"] as stream:
            data = await stream.read()
        assert data == body, "содержимое не совпало!"
        print("✅ get_object   — содержимое совпадает")

        # 4. DELETE (убираем за собой)
        await s3.delete_object(Bucket=bucket, Key=key)
        print("✅ delete_object — тестовый объект удалён")

    print("-" * 50)
    print("🎉 Хранилище рабочее. Бэкапы можно включать.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
