from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.services import training_service

router = APIRouter(prefix="/training", tags=["training"])


class ModuleOut(BaseModel):
    id: str
    slug: str
    title: str
    summary: str
    body: str
    minutes: int
    order_index: int
    completed: bool


class ProgressOut(BaseModel):
    completed: int
    total: int


@router.get("/modules", response_model=list[ModuleOut])
async def list_modules(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ModuleOut]:
    rows = await training_service.list_modules(db, user)
    return [
        ModuleOut(
            id=module.id,
            slug=module.slug,
            title=module.title,
            summary=module.summary,
            body=module.body,
            minutes=module.minutes,
            order_index=module.order_index,
            completed=completed,
        )
        for module, completed in rows
    ]


@router.post("/modules/{module_id}/complete", response_model=ProgressOut)
async def complete_module(
    module_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProgressOut:
    modules = {module.id: module for module, _ in await training_service.list_modules(db, user)}
    if module_id not in modules:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Training module not found")
    await training_service.complete_module(db, user, module_id)
    completed, total = await training_service.training_progress(db, user)
    return ProgressOut(completed=completed, total=total)
