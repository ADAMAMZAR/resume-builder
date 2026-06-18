import uuid

from pydantic import BaseModel


class SkillCreate(BaseModel):
    skill_name: str
    category: str
    proficiency_level: str | None = None
    context: str | None = None


class SkillOut(SkillCreate):
    id: uuid.UUID

    model_config = {"from_attributes": True}
