import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import SkillsInventory
from app.schemas.skills import SkillCreate


async def list_skills(db: AsyncSession, user_id: uuid.UUID) -> list[SkillsInventory]:
    result = await db.execute(select(SkillsInventory).where(SkillsInventory.user_id == user_id))
    return list(result.scalars().all())


async def create_skill(db: AsyncSession, user_id: uuid.UUID, data: SkillCreate) -> SkillsInventory:
    skill = SkillsInventory(user_id=user_id, **data.model_dump())
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    return skill
