import uuid
from datetime import datetime

from pydantic import BaseModel


class ExtractedSkills(BaseModel):
    hard_skills: list[str]
    soft_skills: list[str]
    tools_and_frameworks: list[str]


class WorkExperience(BaseModel):
    company: str
    role: str
    impact_bullets: list[str]


class TailoredResumeSchema(BaseModel):
    summary: str
    skills_aligned: list[str]
    experience: list[WorkExperience]


class ApplicationCreate(BaseModel):
    company_name: str
    role_title: str
    jd_text: str


class ApplicationOut(BaseModel):
    id: uuid.UUID
    company_name: str
    role_title: str
    status: str
    extracted_skills: dict | None = None
    approved_skills: list[str] | None = None
    final_resume_json: dict | None = None
    final_cover_letter_md: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PendingApprovalOut(BaseModel):
    id: uuid.UUID
    extracted_skills: dict


class ApproveRequest(BaseModel):
    approved_skills: list[str]
