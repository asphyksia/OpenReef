import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.dataset import Dataset
from app.models.user import User
from app.schemas.dataset import DatasetResponse
from app.services import dataset_service, storage_service

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


@router.get("", response_model=list[DatasetResponse])
async def list_datasets(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Dataset).where(Dataset.user_id == user.id).order_by(Dataset.created_at.desc())
    )
    datasets = result.scalars().all()
    return [_to_response(d) for d in datasets]


@router.post("", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    file: UploadFile,
    name: str | None = Form(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Check size from headers; if unavailable, enforce during streaming
    if file.size is not None and file.size > dataset_service.MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dataset exceeds maximum size of {dataset_service.MAX_SIZE_BYTES / (1024*1024):.0f}MB",
        )

    filename = file.filename or "unknown"
    fmt = _detect_format(filename)

    # Validate from stream (reads line-by-line, enforces MAX_SIZE_BYTES)
    row_count, token_count, errors = dataset_service.validate_dataset_stream(file.file, fmt)

    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="; ".join(errors),
        )

    # Enforce size limit during streaming upload
    file.file.seek(0, 2)  # seek to end
    actual_size = file.file.tell()
    file.file.seek(0)
    if actual_size > dataset_service.MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dataset exceeds maximum size of {dataset_service.MAX_SIZE_BYTES / (1024*1024):.0f}MB",
        )

    # Stream to object storage (no full read into memory)
    r2_key = f"datasets/{user.id}/{uuid.uuid4()}/{filename}"
    content_type = "text/csv" if fmt == "csv" else "application/octet-stream"
    storage_service.upload_stream(file.file, r2_key, content_type=content_type)

    size = actual_size

    download_url = storage_service.presigned_url(r2_key)

    dataset = Dataset(
        user_id=user.id,
        name=name or filename,
        filename=filename,
        format=fmt,
        size_bytes=size,
        row_count=row_count,
        token_count=token_count,
        validation_status="valid",
        validation_errors=[],
        r2_key=r2_key,
    )
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)

    return _to_response(dataset, r2_url=download_url)


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    dataset = await db.get(Dataset, dataset_id)
    if dataset is None or dataset.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    return _to_response(dataset)


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(
    dataset_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    dataset = await db.get(Dataset, dataset_id)
    if dataset is None or dataset.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    if dataset.r2_key:
        storage_service.delete_file(dataset.r2_key)
    await db.delete(dataset)
    await db.commit()


def _detect_format(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "jsonl":
        return "jsonl"
    elif ext == "csv":
        return "csv"
    elif ext == "txt":
        return "txt"
    return "jsonl"  # default


def _to_response(d: Dataset, r2_url: str | None = None) -> DatasetResponse:
    return DatasetResponse(
        id=d.id,
        name=d.name,
        filename=d.filename,
        format=d.format,
        size_bytes=d.size_bytes,
        row_count=d.row_count,
        token_count=d.token_count,
        validation_status=d.validation_status,
        validation_errors=d.validation_errors or [],
        created_at=d.created_at.isoformat() if d.created_at else "",
        download_url=r2_url,
    )
