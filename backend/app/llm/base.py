from abc import ABC, abstractmethod

from app.schemas.applications import ExtractedSkills, TailoredResumeSchema


class ExtractionClient(ABC):
    @abstractmethod
    async def extract_skills(self, jd_text: str) -> ExtractedSkills: ...


class DraftingClient(ABC):
    @abstractmethod
    async def draft(self, approved_skills: list[str], jd_text: str) -> tuple[TailoredResumeSchema, str]: ...


class JudgeClient(ABC):
    @abstractmethod
    async def polish(
        self, resume: TailoredResumeSchema, cover_letter_md: str
    ) -> tuple[TailoredResumeSchema, str]: ...
