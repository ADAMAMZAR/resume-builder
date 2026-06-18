from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.repositories import skills_repo
from app.schemas.skills import SkillCreate, SkillOut

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.get("", response_model=list[SkillOut])
async def list_skills_route(
    user_id=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await skills_repo.list_skills(db, user_id)


@router.post("", response_model=SkillOut, status_code=status.HTTP_201_CREATED)
async def create_skill_route(
    payload: SkillCreate,
    user_id=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await skills_repo.create_skill(db, user_id, payload)
