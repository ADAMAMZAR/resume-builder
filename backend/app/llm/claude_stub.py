from app.llm.base import JudgeClient
from app.schemas.applications import TailoredResumeSchema


class ClaudeStubClient(JudgeClient):
    async def polish(
        self, resume: TailoredResumeSchema, cover_letter_md: str
    ) -> tuple[TailoredResumeSchema, str]:
        polished_resume = resume.model_copy(update={"summary": resume.summary + " (polished)"})
        polished_cover_letter = cover_letter_md + "\n\n(polished)"
        return polished_resume, polished_cover_letter
