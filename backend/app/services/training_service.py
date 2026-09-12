"""Role-based enablement content and completion tracking."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.training import TrainingCompletion, TrainingModule
from app.models.user import User


async def list_modules(db: AsyncSession, user: User) -> list[tuple[TrainingModule, bool]]:
    modules = (
        (await db.execute(select(TrainingModule).order_by(TrainingModule.order_index)))
        .scalars()
        .all()
    )
    completed_ids = set(
        (
            await db.execute(
                select(TrainingCompletion.module_id).where(TrainingCompletion.user_id == user.id)
            )
        )
        .scalars()
        .all()
    )
    relevant = [
        module
        for module in modules
        if not module.target_roles or user.job_role in module.target_roles
    ]
    return [(module, module.id in completed_ids) for module in relevant]


async def complete_module(db: AsyncSession, user: User, module_id: str) -> bool:
    existing = (
        await db.execute(
            select(TrainingCompletion).where(
                TrainingCompletion.user_id == user.id,
                TrainingCompletion.module_id == module_id,
            )
        )
    ).scalars().first()
    if existing:
        return False
    db.add(TrainingCompletion(user_id=user.id, module_id=module_id))
    await db.commit()
    return True


async def training_progress(db: AsyncSession, user: User) -> tuple[int, int]:
    modules = await list_modules(db, user)
    total = len(modules)
    completed = sum(1 for _, done in modules if done)
    return completed, total


async def module_count(db: AsyncSession) -> int:
    return (await db.execute(select(func.count(TrainingModule.id)))).scalar_one()
