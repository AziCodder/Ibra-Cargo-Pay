"""
Проверка dual-write хранилища: каждый таргет по отдельности + сквозная запись через
storage_service (пишет во все таргеты сразу). Ничего в бакетах не оставляет.

Запуск ВНУТРИ backend-контейнера:
    docker compose exec backend python scripts/test_storage.py
"""

import asyncio
import sys
from datetime import datetime, timezone

from app.services import storage_service


async def _check_target(t: storage_service.S3Target) -> bool:
    key = f"_selftest/{t.name}_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}.txt"
    body = f"dual-write self-test [{t.name}] — safe to delete".encode()
    print(f"\n▶ Таргет '{t.name}'  endpoint={t.endpoint_url}  bucket={t.bucket}")
    try:
        async with storage_service.client(t) as s3:
            await s3.put_object(Bucket=t.bucket, Key=key, Body=body)
            print("  ✅ put")
            resp = await s3.get_object(Bucket=t.bucket, Key=key)
            async with resp["Body"] as stream:
                data = await stream.read()
            assert data == body, "содержимое не совпало"
            print("  ✅ get + целостность")
            await s3.delete_object(Bucket=t.bucket, Key=key)
            print("  ✅ delete")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  ❌ ОШИБКА: {e}")
        return False


async def _check_dual() -> bool:
    """Сквозная проверка: put через storage_service → объект есть в КАЖДОМ таргете."""
    targets = storage_service.file_targets()
    key = f"_selftest/dual_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}.txt"
    body = b"dual-write end-to-end"
    print(f"\n▶ Сквозная запись storage_service.put в {len(targets)} таргет(ов)")
    try:
        await storage_service.put(key, body)
        ok_all = True
        for t in targets:
            async with storage_service.client(t) as s3:
                try:
                    await s3.head_object(Bucket=t.bucket, Key=key)
                    print(f"  ✅ объект есть в '{t.name}'")
                except Exception:
                    print(f"  ❌ объекта НЕТ в '{t.name}'")
                    ok_all = False
        await storage_service.delete(key)
        print("  ✅ убрано из всех таргетов")
        return ok_all
    except Exception as e:  # noqa: BLE001
        print(f"  ❌ ОШИБКА: {e}")
        return False


async def main() -> int:
    targets = storage_service.file_targets()
    if not targets:
        print("❌ Нет настроенных S3-таргетов (проверь S3_* / S3_SECONDARY_* в .env)")
        return 1
    print(f"Настроено таргетов: {len(targets)} — {[t.name for t in targets]}")
    if len(targets) < 2:
        print("⚠️  dual-write неактивен: настроен только один таргет "
              "(добавь S3_SECONDARY_* для второго хранилища)")

    ok = True
    for t in targets:
        ok = await _check_target(t) and ok
    if len(targets) >= 2:
        ok = await _check_dual() and ok

    print("\n" + ("🎉 Все проверки пройдены." if ok else "❌ Есть ошибки — см. выше."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
