import uuid

from sqlalchemy import SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String, nullable=False)
    role_title: Mapped[str] = mapped_column(String, nullable=False)
    jd_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending_extraction")
    extracted_skills: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    extracted_skills_version: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    approved_skills: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    approved_skills_version: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    final_resume_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    final_cover_letter_md: Mapped[str | None] = mapped_column(Text, nullable=True)
