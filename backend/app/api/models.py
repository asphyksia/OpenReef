from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.base_model import BaseModel as DBBaseModel
from app.models.user import User
from app.services.pricing import PRESET_DISPLAY

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("")
async def list_models(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(DBBaseModel).where(DBBaseModel.is_active == True))
    models = result.scalars().all()
    return {
        "models": [
            {
                "id": m.id,
                "name": m.name,
                "param_count": m.param_count,
                "min_vram_gb": m.min_vram_gb,
                "supported_adapters": m.supported_adapters,
            }
            for m in models
        ],
        "presets": PRESET_DISPLAY,
    }
