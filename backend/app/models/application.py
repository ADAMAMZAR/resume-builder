import uuid
from datetime import datetime

from sqlalchemy import SmallInteger, String, Text, TIMESTAMP, func
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
    # server_default is required: SQLAlchemy's ORM only omits a column from the
    # generated INSERT (letting the DB's DEFAULT fire) when the column has a
    # Python-side default/default_factory OR a server_default marker. With neither,
    # the unset attribute is sent as an explicit NULL parameter, which violates the
    # NOT NULL constraint from migrations/001_init.sql (verified via failing
    # NotNullViolationError when server_default was removed).
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
