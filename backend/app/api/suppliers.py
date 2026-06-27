from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.supplier import Supplier
from app.schemas.supplier import SupplierBrief, SupplierCreate, SupplierListOut, SupplierOut, SupplierUpdate
from app.services import audit_service, file_service

MAX_DOC_SIZE = 10 * 1024 * 1024  # 10 МБ

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


@router.get("/brief", response_model=list[SupplierBrief])
async def list_suppliers_brief(
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SupplierBrief]:
    result = await db.execute(
        select(Supplier).order_by(Supplier.full_name.asc())
    )
    return [SupplierBrief.model_validate(s) for s in result.scalars().all()]


@router.get("", response_model=SupplierListOut)
async def list_suppliers(
    page: int = 1,
    page_size: int = 50,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SupplierListOut:
    offset = (page - 1) * page_size
    total_result = await db.execute(select(func.count()).select_from(Supplier))
    total = total_result.scalar_one()

    result = await db.execute(
        select(Supplier).order_by(Supplier.created_at.desc()).offset(offset).limit(page_size)
    )
    suppliers = result.scalars().all()
    return SupplierListOut(
        items=[SupplierOut.model_validate(s) for s in suppliers],
        total=total,
    )


@router.post("", response_model=SupplierOut, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    data: SupplierCreate,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SupplierOut:
    supplier = Supplier(
        full_name=data.full_name,
        phone=data.phone,
        wechat_id=data.wechat_id,
        document_1=data.document_1,
        document_2=data.document_2,
        document_3=data.document_3,
        description=data.description,
    )
    db.add(supplier)
    await db.flush()

    await audit_service.log_action(
        db,
        user_id=current_user.id,
        action="created",
        entity_type="supplier",
        entity_id=supplier.id,
        after=audit_service.entity_snapshot(supplier),
    )

    await db.commit()
    await db.refresh(supplier)
    return SupplierOut.model_validate(supplier)


@router.get("/{supplier_id}", response_model=SupplierOut)
async def get_supplier(
    supplier_id: int,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SupplierOut:
    supplier = await db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Поставщик не найден")
    return SupplierOut.model_validate(supplier)


@router.put("/{supplier_id}", response_model=SupplierOut)
async def update_supplier(
    supplier_id: int,
    data: SupplierUpdate,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SupplierOut:
    supplier = await db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Поставщик не найден")

    before = audit_service.entity_snapshot(supplier)

    if data.full_name is not None:
        supplier.full_name = data.full_name
    if data.phone is not None:
        supplier.phone = data.phone
    if data.wechat_id is not None:
        supplier.wechat_id = data.wechat_id
    if data.document_1 is not None:
        supplier.document_1 = data.document_1 or None
    if data.document_2 is not None:
        supplier.document_2 = data.document_2 or None
    if data.document_3 is not None:
        supplier.document_3 = data.document_3 or None
    if data.description is not None:
        supplier.description = data.description

    await db.flush()
    after = audit_service.entity_snapshot(supplier)

    await audit_service.log_action(
        db,
        user_id=current_user.id,
        action="updated",
        entity_type="supplier",
        entity_id=supplier.id,
        before=before,
        after=after,
    )

    await db.commit()
    await db.refresh(supplier)
    return SupplierOut.model_validate(supplier)


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_supplier(
    supplier_id: int,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    supplier = await db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Поставщик не найден")

    before = audit_service.entity_snapshot(supplier)
    supplier_id_snapshot = supplier.id

    # Удаление разрешено — FK SET NULL обработает привязку к товарам
    await db.delete(supplier)

    await audit_service.log_action(
        db,
        user_id=current_user.id,
        action="deleted",
        entity_type="supplier",
        entity_id=supplier_id_snapshot,
        before=before,
    )

    await db.commit()


@router.post("/{supplier_id}/documents", response_model=SupplierOut)
async def upload_supplier_document(
    supplier_id: int,
    slot: int = Form(...),
    file: UploadFile = File(...),
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SupplierOut:
    """Загружает файл в слот документа поставщика (slot: 1, 2 или 3)."""
    if slot not in (1, 2, 3):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Слот должен быть 1, 2 или 3",
        )
    supplier = await db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Поставщик не найден")

    original_name = file.filename or "document"
    try:
        file_service.validate_file_extension(original_name)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_DOC_SIZE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Файл слишком большой. Максимум 10 МБ",
        )

    field_name = f"document_{slot}"
    old_key: str | None = getattr(supplier, field_name)
    if old_key:
        await file_service.delete_file(old_key)

    new_key = await file_service.upload_file(file_bytes, original_name, prefix="suppliers")
    # Формат хранения: "s3key|original_filename" — ключ для S3 и имя для отображения
    setattr(supplier, field_name, f"{new_key}|{original_name}")
    await db.commit()
    await db.refresh(supplier)
    return SupplierOut.model_validate(supplier)


@router.delete("/{supplier_id}/documents/{slot}", response_model=SupplierOut)
async def delete_supplier_document(
    supplier_id: int,
    slot: int,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SupplierOut:
    """Удаляет файл из слота документа поставщика (slot: 1, 2 или 3)."""
    if slot not in (1, 2, 3):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Слот должен быть 1, 2 или 3",
        )
    supplier = await db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Поставщик не найден")

    field_name = f"document_{slot}"
    raw_value: str | None = getattr(supplier, field_name)
    if raw_value:
        s3_key = raw_value.split("|")[0]
        await file_service.delete_file(s3_key)
        setattr(supplier, field_name, None)
        await db.commit()
        await db.refresh(supplier)

    return SupplierOut.model_validate(supplier)
