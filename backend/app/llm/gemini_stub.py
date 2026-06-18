from app.llm.base import DraftingClient, ExtractionClient
from app.schemas.applications import ExtractedSkills, TailoredResumeSchema, WorkExperience


class GeminiStubClient(ExtractionClient, DraftingClient):
    async def extract_skills(self, jd_text: str) -> ExtractedSkills:
        return ExtractedSkills(
            hard_skills=["Python", "SQL"],
            soft_skills=["Communication"],
            tools_and_frameworks=["FastAPI"],
        )

    async def draft(self, approved_skills: list[str], jd_text: str) -> tuple[TailoredResumeSchema, str]:
        resume = TailoredResumeSchema(
            summary="Stub summary tailored to the role.",
            skills_aligned=approved_skills,
            experience=[
                WorkExperience(
                    company="Acme Corp",
                    role="Software Engineer",
                    impact_bullets=["Shipped a stub feature."],
                )
            ],
        )
        cover_letter_md = "# Cover Letter\n\nStub cover letter body."
        return resume, cover_letter_md
