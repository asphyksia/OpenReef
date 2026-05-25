from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.base_model import BaseModel as DBBaseModel
from app.models.user import User

router = APIRouter(prefix="/api/models", tags=["models"])

PRESETS = {
    "fast": {"label": "Fast", "description": "Quick training, fewer epochs. Good for testing.", "epochs": 1, "learning_rate": 2e-4},
    "balanced": {"label": "Balanced", "description": "Good quality/price ratio.", "epochs": 2, "learning_rate": 1e-4},
    "quality": {"label": "Quality", "description": "More epochs, best results.", "epochs": 3, "learning_rate": 5e-5},
}


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
        "presets": PRESETS,
    }
