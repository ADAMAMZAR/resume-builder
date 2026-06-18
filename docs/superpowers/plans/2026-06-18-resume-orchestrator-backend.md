# Resume Orchestrator Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI backend state machine for the resume/cover-letter orchestrator, with API-key auth, app-layer data isolation, conditional-UPDATE state transitions (concurrency + idempotency guard), and stub LLM clients, per the approved spec at `docs/superpowers/specs/2026-06-18-resume-orchestrator-backend-design.md`.

**Architecture:** FastAPI + async SQLAlchemy + asyncpg against Postgres (docker-compose locally). Every DB query is scoped by `user_id` resolved from an `X-API-Key` header. State transitions are single conditional `UPDATE ... WHERE status = :expected` statements — a 0-rowcount result distinguishes "not yours" (404) from "wrong state" (409). LLM calls go through a stub `LLMClient` interface so the pipeline is fully testable without API keys.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (async), asyncpg, Pydantic v2, pydantic-settings, pytest + pytest-asyncio + httpx, Postgres 16 via docker-compose.

---

## File Structure

```
resume-builder/
  docker-compose.yml
  docker/init-test-db.sh
  .env.example
  requirements.txt
  pytest.ini
  migrations/
    001_init.sql
  backend/
    app/
      __init__.py
      main.py
      config.py
      db.py
      deps.py
      models/
        __init__.py
        api_key.py
        skill.py
        application.py
      schemas/
        __init__.py
        skills.py
        applications.py
      llm/
        __init__.py
        base.py
        gemini_stub.py
        claude_stub.py
      repositories/
        __init__.py
        skills_repo.py
        applications_repo.py
      routers/
        __init__.py
        skills.py
        applications.py
    tests/
      __init__.py
      conftest.py
      test_skills.py
      test_applications_flow.py
```

---

### Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `docker-compose.yml`
- Create: `docker/init-test-db.sh`
- Create: `.env.example`
- Create: `pytest.ini`
- Create: `backend/app/__init__.py` (empty)
- Create: `backend/tests/__init__.py` (empty)

- [ ] **Step 1: Write `requirements.txt`**

```text
fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy[asyncio]==2.0.35
asyncpg==0.29.0
pydantic==2.9.2
pydantic-settings==2.5.2
python-dotenv==1.0.1
httpx==0.27.2
pytest==8.3.3
pytest-asyncio==0.24.0
```

- [ ] **Step 2: Write `docker-compose.yml`**

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: resume_orchestrator
    ports:
      - "5432:5432"
    volumes:
      - ./docker/init-test-db.sh:/docker-entrypoint-initdb.d/init-test-db.sh
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

- [ ] **Step 3: Write `docker/init-test-db.sh`**

```bash
#!/bin/bash
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE resume_orchestrator_test;
EOSQL
```

- [ ] **Step 4: Write `.env.example`**

```text
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/resume_orchestrator
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/resume_orchestrator_test
```

- [ ] **Step 5: Write `pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 6: Create empty `backend/app/__init__.py` and `backend/tests/__init__.py`**

Both files are empty — they just make `app` and `tests` importable packages.

- [ ] **Step 7: Start the database**

Run: `docker compose up -d db`
Expected: container starts, `docker compose ps` shows `db` as `healthy` or `running`.

- [ ] **Step 8: Install Python dependencies**

Run: `pip install -r requirements.txt`
Expected: no errors.

- [ ] **Step 9: Commit**

```bash
git add requirements.txt docker-compose.yml docker/init-test-db.sh .env.example pytest.ini backend/app/__init__.py backend/tests/__init__.py
git commit -m "chore: project scaffolding for backend (docker, deps, pytest config)"
```

---

### Task 2: DB engine, config, and migration SQL

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/app/db.py`
- Create: `migrations/001_init.sql`

- [ ] **Step 1: Write `backend/app/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
```

- [ ] **Step 2: Write `backend/app/db.py`**

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

- [ ] **Step 3: Write `migrations/001_init.sql`**

```sql
CREATE TABLE api_keys (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL UNIQUE,
    key_hash TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE skills_inventory (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES api_keys(user_id),
    skill_name TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('hard_skill', 'soft_skill', 'tool')),
    proficiency_level TEXT,
    context TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_skills_inventory_user_id ON skills_inventory(user_id);

CREATE TABLE applications (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES api_keys(user_id),
    company_name TEXT NOT NULL,
    role_title TEXT NOT NULL,
    jd_text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending_extraction' CHECK (
        status IN (
            'pending_extraction',
            'extraction_failed',
            'awaiting_human',
            'generating',
            'generation_failed',
            'completed'
        )
    ),
    extracted_skills JSONB,
    extracted_skills_version SMALLINT NOT NULL DEFAULT 1,
    approved_skills JSONB,
    approved_skills_version SMALLINT NOT NULL DEFAULT 1,
    final_resume_json JSONB,
    final_cover_letter_md TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_applications_user_id ON applications(user_id);
```

- [ ] **Step 4: Apply the migration to the dev database**

Run: `docker exec -i $(docker compose ps -q db) psql -U postgres -d resume_orchestrator < migrations/001_init.sql`
Expected: `CREATE TABLE` x3, `CREATE INDEX` x2, no errors.

- [ ] **Step 5: Copy `.env.example` to `.env`**

Run: `cp .env.example .env`
Expected: `.env` exists with `DATABASE_URL` and `TEST_DATABASE_URL` set.

- [ ] **Step 6: Commit**

```bash
git add backend/app/config.py backend/app/db.py migrations/001_init.sql
git commit -m "feat: db engine config and initial schema migration"
```

(`.env` is local-only — do not commit it. Add `.env` to a new `.gitignore` if one doesn't exist.)

- [ ] **Step 7: Add `.gitignore`**

```text
.env
__pycache__/
*.pyc
.pytest_cache/
```

Run: `git add .gitignore && git commit -m "chore: add gitignore"`

---

### Task 3: SQLAlchemy models

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/api_key.py`
- Create: `backend/app/models/skill.py`
- Create: `backend/app/models/application.py`

- [ ] **Step 1: Write `backend/app/models/__init__.py`**

```python
from app.models.api_key import ApiKey
from app.models.application import Application
from app.models.skill import SkillsInventory

__all__ = ["ApiKey", "Application", "SkillsInventory"]
```

- [ ] **Step 2: Write `backend/app/models/api_key.py`**

```python
import uuid

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    key_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
```

- [ ] **Step 3: Write `backend/app/models/skill.py`**

```python
import uuid

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SkillsInventory(Base):
    __tablename__ = "skills_inventory"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    skill_name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    proficiency_level: Mapped[str | None] = mapped_column(String, nullable=True)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 4: Write `backend/app/models/application.py`**

```python
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
```

- [ ] **Step 5: Verify models import cleanly**

Run: `cd backend && python -c "from app.models import ApiKey, Application, SkillsInventory; print('ok')"`
Expected: `ok`

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/
git commit -m "feat: SQLAlchemy models for api_keys, skills_inventory, applications"
```

---

### Task 4: Pydantic schemas

**Files:**
- Create: `backend/app/schemas/__init__.py` (empty)
- Create: `backend/app/schemas/skills.py`
- Create: `backend/app/schemas/applications.py`

- [ ] **Step 1: Write `backend/app/schemas/skills.py`**

```python
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
```

- [ ] **Step 2: Write `backend/app/schemas/applications.py`**

```python
import uuid

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

    model_config = {"from_attributes": True}


class PendingApprovalOut(BaseModel):
    id: uuid.UUID
    extracted_skills: dict


class ApproveRequest(BaseModel):
    approved_skills: list[str]
```

- [ ] **Step 3: Verify schemas import cleanly**

Run: `cd backend && python -c "from app.schemas.applications import ExtractedSkills, ApplicationOut; from app.schemas.skills import SkillOut; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/
git commit -m "feat: Pydantic schemas for skills and applications"
```

---

### Task 5: LLM stub clients

**Files:**
- Create: `backend/app/llm/__init__.py` (empty)
- Create: `backend/app/llm/base.py`
- Create: `backend/app/llm/gemini_stub.py`
- Create: `backend/app/llm/claude_stub.py`

- [ ] **Step 1: Write `backend/app/llm/base.py`**

```python
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
```

- [ ] **Step 2: Write `backend/app/llm/gemini_stub.py`**

```python
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
```

- [ ] **Step 3: Write `backend/app/llm/claude_stub.py`**

```python
from app.llm.base import JudgeClient
from app.schemas.applications import TailoredResumeSchema


class ClaudeStubClient(JudgeClient):
    async def polish(
        self, resume: TailoredResumeSchema, cover_letter_md: str
    ) -> tuple[TailoredResumeSchema, str]:
        polished_resume = resume.model_copy(update={"summary": resume.summary + " (polished)"})
        polished_cover_letter = cover_letter_md + "\n\n(polished)"
        return polished_resume, polished_cover_letter
```

- [ ] **Step 4: Verify stub clients work standalone**

Run:
```bash
cd backend && python -c "
import asyncio
from app.llm.gemini_stub import GeminiStubClient
from app.llm.claude_stub import ClaudeStubClient

async def main():
    g = GeminiStubClient()
    extracted = await g.extract_skills('some jd')
    resume, cover = await g.draft(['Python'], 'some jd')
    c = ClaudeStubClient()
    polished_resume, polished_cover = await c.polish(resume, cover)
    assert polished_resume.summary.endswith('(polished)')
    assert polished_cover.endswith('(polished)')
    print('ok')

asyncio.run(main())
"
```
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add backend/app/llm/
git commit -m "feat: stub Gemini/Claude LLM clients behind shared interface"
```

---

### Task 6: Auth dependency

**Files:**
- Create: `backend/app/deps.py`

- [ ] **Step 1: Write `backend/app/deps.py`**

```python
import hashlib
import uuid

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.api_key import ApiKey


async def get_current_user(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    if x_api_key is None:
        raise HTTPException(status_code=401, detail="missing X-API-Key header")

    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    result = await db.execute(select(ApiKey).where(ApiKey.key_hash == key_hash))
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise HTTPException(status_code=401, detail="invalid API key")

    return api_key.user_id
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `cd backend && python -c "from app.deps import get_current_user; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/app/deps.py
git commit -m "feat: API-key auth dependency resolving request user_id"
```

---

### Task 7: Repositories

**Files:**
- Create: `backend/app/repositories/__init__.py` (empty)
- Create: `backend/app/repositories/skills_repo.py`
- Create: `backend/app/repositories/applications_repo.py`

- [ ] **Step 1: Write `backend/app/repositories/skills_repo.py`**

```python
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
```

- [ ] **Step 2: Write `backend/app/repositories/applications_repo.py`**

```python
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.schemas.applications import ApplicationCreate


async def create_application(db: AsyncSession, user_id: uuid.UUID, data: ApplicationCreate) -> Application:
    app_row = Application(
        user_id=user_id,
        company_name=data.company_name,
        role_title=data.role_title,
        jd_text=data.jd_text,
        status="pending_extraction",
    )
    db.add(app_row)
    await db.commit()
    await db.refresh(app_row)
    return app_row


async def get_application(db: AsyncSession, user_id: uuid.UUID, app_id: uuid.UUID) -> Application | None:
    result = await db.execute(
        select(Application).where(Application.id == app_id, Application.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_status_conditional(
    db: AsyncSession,
    app_id: uuid.UUID,
    user_id: uuid.UUID,
    expected_status: str,
    next_status: str,
    **fields,
) -> bool:
    stmt = (
        update(Application)
        .where(
            Application.id == app_id,
            Application.user_id == user_id,
            Application.status == expected_status,
        )
        .values(status=next_status, **fields)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount == 1
```

- [ ] **Step 3: Verify repositories import cleanly**

Run: `cd backend && python -c "from app.repositories import skills_repo, applications_repo; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/app/repositories/
git commit -m "feat: user-scoped repositories with conditional status-transition update"
```

---

### Task 8: Test infrastructure (conftest)

**Files:**
- Create: `backend/tests/conftest.py`

This sets up the test database fixtures used by every test in Tasks 9–11. Each request in tests gets its **own** DB session/connection (not a shared one) so that concurrent-request tests in Task 11 exercise real database-level row locking instead of a single Python object serializing everything.

- [ ] **Step 1: Write `backend/tests/conftest.py`**

```python
import asyncio
import hashlib
import os
import pathlib
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import get_db
from app.main import app
from app.models.api_key import ApiKey

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/resume_orchestrator_test",
)
MIGRATION_PATH = pathlib.Path(__file__).resolve().parents[2] / "migrations" / "001_init.sql"

test_engine = create_async_engine(TEST_DATABASE_URL)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def apply_migrations():
    sql = MIGRATION_PATH.read_text()
    async with test_engine.begin() as conn:
        await conn.exec_driver_sql(
            "DROP TABLE IF EXISTS applications, skills_inventory, api_keys CASCADE"
        )
        await conn.exec_driver_sql(sql)
    yield


@pytest_asyncio.fixture(autouse=True)
async def clean_tables():
    yield
    async with test_engine.begin() as conn:
        await conn.exec_driver_sql("TRUNCATE applications, skills_inventory, api_keys CASCADE")


@pytest_asyncio.fixture
async def db_session():
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    async def override_get_db():
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def api_key(db_session):
    user_id = uuid.uuid4()
    raw_key = f"test-key-{user_id}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    db_session.add(ApiKey(id=uuid.uuid4(), user_id=user_id, key_hash=key_hash))
    await db_session.commit()
    return {"user_id": user_id, "raw_key": raw_key, "headers": {"X-API-Key": raw_key}}
```

This references `app.main`, which doesn't exist yet — that's built in Task 9 alongside the first router. This task's "verify" step happens at the start of Task 9 once `main.py` exists.

- [ ] **Step 2: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "test: shared fixtures for test db, isolated sessions per request, api keys"
```

---

### Task 9: Skills router (TDD)

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/app/routers/__init__.py` (empty)
- Create: `backend/app/routers/skills.py`
- Create: `backend/tests/test_skills.py`

- [ ] **Step 1: Write minimal `backend/app/main.py` (no routers yet)**

```python
from fastapi import FastAPI

app = FastAPI(title="Resume Orchestrator")
```

- [ ] **Step 2: Write the failing test in `backend/tests/test_skills.py`**

```python
async def test_create_and_list_skill(client, api_key):
    create_resp = await client.post(
        "/api/skills",
        json={
            "skill_name": "Python",
            "category": "hard_skill",
            "proficiency_level": "expert",
            "context": "5 years building backend services",
        },
        headers=api_key["headers"],
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["skill_name"] == "Python"
    assert created["category"] == "hard_skill"

    list_resp = await client.get("/api/skills", headers=api_key["headers"])
    assert list_resp.status_code == 200
    skills = list_resp.json()
    assert len(skills) == 1
    assert skills[0]["skill_name"] == "Python"


async def test_missing_api_key_returns_401(client):
    resp = await client.get("/api/skills")
    assert resp.status_code == 401


async def test_invalid_api_key_returns_401(client):
    resp = await client.get("/api/skills", headers={"X-API-Key": "not-a-real-key"})
    assert resp.status_code == 401
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_skills.py -v`
Expected: FAIL — `404 Not Found` for `/api/skills` (no router registered yet).

- [ ] **Step 4: Write `backend/app/routers/skills.py`**

```python
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
```

- [ ] **Step 5: Update `backend/app/main.py` to register the router**

```python
from fastapi import FastAPI

from app.routers import skills

app = FastAPI(title="Resume Orchestrator")
app.include_router(skills.router)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_skills.py -v`
Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add backend/app/main.py backend/app/routers/__init__.py backend/app/routers/skills.py backend/tests/test_skills.py
git commit -m "feat: skills CRUD router with auth + isolation tests"
```

---

### Task 10: Applications router — create & pending-approval (TDD)

**Files:**
- Create: `backend/app/routers/applications.py`
- Create: `backend/tests/test_applications_flow.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write the failing tests in `backend/tests/test_applications_flow.py`**

```python
async def test_create_application_extracts_skills_and_awaits_human(client, api_key):
    resp = await client.post(
        "/api/applications",
        json={
            "company_name": "Acme Corp",
            "role_title": "Backend Engineer",
            "jd_text": "Looking for someone strong in Python and SQL.",
        },
        headers=api_key["headers"],
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "awaiting_human"
    assert "Python" in body["extracted_skills"]["hard_skills"]


async def test_pending_approval_returns_extracted_skills(client, api_key):
    create_resp = await client.post(
        "/api/applications",
        json={"company_name": "Acme", "role_title": "Engineer", "jd_text": "JD text"},
        headers=api_key["headers"],
    )
    app_id = create_resp.json()["id"]

    resp = await client.get(f"/api/applications/{app_id}/pending-approval", headers=api_key["headers"])
    assert resp.status_code == 200
    assert "hard_skills" in resp.json()["extracted_skills"]


async def test_pending_approval_for_other_users_application_returns_404(client, api_key, db_session):
    import hashlib
    import uuid

    from app.models.api_key import ApiKey

    create_resp = await client.post(
        "/api/applications",
        json={"company_name": "Acme", "role_title": "Engineer", "jd_text": "JD text"},
        headers=api_key["headers"],
    )
    app_id = create_resp.json()["id"]

    other_user_id = uuid.uuid4()
    other_raw_key = f"other-key-{other_user_id}"
    other_hash = hashlib.sha256(other_raw_key.encode()).hexdigest()
    db_session.add(ApiKey(id=uuid.uuid4(), user_id=other_user_id, key_hash=other_hash))
    await db_session.commit()

    resp = await client.get(
        f"/api/applications/{app_id}/pending-approval",
        headers={"X-API-Key": other_raw_key},
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_applications_flow.py -v`
Expected: FAIL — `404 Not Found`, no `/api/applications` route registered yet.

- [ ] **Step 3: Write `backend/app/routers/applications.py` (create + pending-approval only)**

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.llm.gemini_stub import GeminiStubClient
from app.repositories import applications_repo
from app.schemas.applications import ApplicationCreate, ApplicationOut, PendingApprovalOut

router = APIRouter(prefix="/api/applications", tags=["applications"])
gemini = GeminiStubClient()


@router.post("", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
async def create_application_route(
    payload: ApplicationCreate,
    user_id=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    app_row = await applications_repo.create_application(db, user_id, payload)

    try:
        extracted = await gemini.extract_skills(payload.jd_text)
    except Exception:
        await applications_repo.update_status_conditional(
            db, app_row.id, user_id, "pending_extraction", "extraction_failed"
        )
        raise HTTPException(status_code=502, detail="skill extraction failed")

    ok = await applications_repo.update_status_conditional(
        db,
        app_row.id,
        user_id,
        "pending_extraction",
        "awaiting_human",
        extracted_skills=extracted.model_dump(),
    )
    if not ok:
        raise HTTPException(status_code=500, detail="unexpected state transition failure")

    await db.refresh(app_row)
    return app_row


@router.get("/{app_id}/pending-approval", response_model=PendingApprovalOut)
async def pending_approval_route(
    app_id: uuid.UUID,
    user_id=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    app_row = await applications_repo.get_application(db, user_id, app_id)
    if app_row is None:
        raise HTTPException(status_code=404, detail="application not found")
    if app_row.status != "awaiting_human":
        raise HTTPException(
            status_code=409,
            detail=f"application is in status '{app_row.status}', expected 'awaiting_human'",
        )
    return PendingApprovalOut(id=app_row.id, extracted_skills=app_row.extracted_skills)
```

- [ ] **Step 4: Register the router in `backend/app/main.py`**

```python
from fastapi import FastAPI

from app.routers import applications, skills

app = FastAPI(title="Resume Orchestrator")
app.include_router(skills.router)
app.include_router(applications.router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_applications_flow.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/applications.py backend/app/main.py backend/tests/test_applications_flow.py
git commit -m "feat: application creation + extraction + pending-approval routes"
```

---

### Task 11: Applications router — approve, generation pipeline, concurrency guard (TDD)

**Files:**
- Modify: `backend/app/routers/applications.py`
- Modify: `backend/tests/test_applications_flow.py`

- [ ] **Step 1: Add failing tests to `backend/tests/test_applications_flow.py`**

```python
async def test_approve_runs_generation_pipeline_to_completion(client, api_key):
    create_resp = await client.post(
        "/api/applications",
        json={"company_name": "Acme", "role_title": "Engineer", "jd_text": "JD text"},
        headers=api_key["headers"],
    )
    app_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/applications/{app_id}/approve",
        json={"approved_skills": ["Python", "SQL"]},
        headers=api_key["headers"],
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["final_resume_json"]["summary"].endswith("(polished)")
    assert body["final_cover_letter_md"].endswith("(polished)")


async def test_approve_on_already_completed_application_returns_409(client, api_key):
    create_resp = await client.post(
        "/api/applications",
        json={"company_name": "Acme", "role_title": "Engineer", "jd_text": "JD text"},
        headers=api_key["headers"],
    )
    app_id = create_resp.json()["id"]

    first = await client.post(
        f"/api/applications/{app_id}/approve",
        json={"approved_skills": []},
        headers=api_key["headers"],
    )
    assert first.status_code == 200

    second = await client.post(
        f"/api/applications/{app_id}/approve",
        json={"approved_skills": []},
        headers=api_key["headers"],
    )
    assert second.status_code == 409


async def test_approve_on_other_users_application_returns_404(client, api_key, db_session):
    import hashlib
    import uuid

    from app.models.api_key import ApiKey

    create_resp = await client.post(
        "/api/applications",
        json={"company_name": "Acme", "role_title": "Engineer", "jd_text": "JD text"},
        headers=api_key["headers"],
    )
    app_id = create_resp.json()["id"]

    other_user_id = uuid.uuid4()
    other_raw_key = f"other-key-{other_user_id}"
    other_hash = hashlib.sha256(other_raw_key.encode()).hexdigest()
    db_session.add(ApiKey(id=uuid.uuid4(), user_id=other_user_id, key_hash=other_hash))
    await db_session.commit()

    resp = await client.post(
        f"/api/applications/{app_id}/approve",
        json={"approved_skills": []},
        headers={"X-API-Key": other_raw_key},
    )
    assert resp.status_code == 404


async def test_concurrent_approve_only_one_request_succeeds(client, api_key):
    import asyncio

    create_resp = await client.post(
        "/api/applications",
        json={"company_name": "Acme", "role_title": "Engineer", "jd_text": "JD text"},
        headers=api_key["headers"],
    )
    app_id = create_resp.json()["id"]

    results = await asyncio.gather(
        client.post(
            f"/api/applications/{app_id}/approve",
            json={"approved_skills": []},
            headers=api_key["headers"],
        ),
        client.post(
            f"/api/applications/{app_id}/approve",
            json={"approved_skills": []},
            headers=api_key["headers"],
        ),
    )
    statuses = sorted(r.status_code for r in results)
    assert statuses == [200, 409]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_applications_flow.py -v`
Expected: FAIL — `404 Not Found` for `POST /api/applications/{id}/approve` (route doesn't exist yet).

- [ ] **Step 3: Add the approve route to `backend/app/routers/applications.py`**

Add these imports at the top (alongside existing ones):

```python
from app.llm.claude_stub import ClaudeStubClient
from app.schemas.applications import ApproveRequest
```

Add this client instance below `gemini = GeminiStubClient()`:

```python
claude = ClaudeStubClient()
```

Append the new route at the end of the file:

```python
@router.post("/{app_id}/approve", response_model=ApplicationOut)
async def approve_route(
    app_id: uuid.UUID,
    payload: ApproveRequest,
    user_id=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    app_row = await applications_repo.get_application(db, user_id, app_id)
    if app_row is None:
        raise HTTPException(status_code=404, detail="application not found")

    ok = await applications_repo.update_status_conditional(
        db,
        app_id,
        user_id,
        "awaiting_human",
        "generating",
        approved_skills=payload.approved_skills,
    )
    if not ok:
        current = await applications_repo.get_application(db, user_id, app_id)
        raise HTTPException(
            status_code=409,
            detail=f"application is in status '{current.status}', expected 'awaiting_human'",
        )

    try:
        resume, cover_letter = await gemini.draft(payload.approved_skills, app_row.jd_text)
        resume, cover_letter = await claude.polish(resume, cover_letter)
    except Exception:
        await applications_repo.update_status_conditional(
            db, app_id, user_id, "generating", "generation_failed"
        )
        raise HTTPException(status_code=502, detail="resume generation failed")

    await applications_repo.update_status_conditional(
        db,
        app_id,
        user_id,
        "generating",
        "completed",
        final_resume_json=resume.model_dump(),
        final_cover_letter_md=cover_letter,
    )

    return await applications_repo.get_application(db, user_id, app_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_applications_flow.py -v`
Expected: 7 passed (3 from Task 10 + 4 new).

- [ ] **Step 5: Run the full test suite**

Run: `cd backend && pytest -v`
Expected: all tests across `test_skills.py` and `test_applications_flow.py` pass (10 total).

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/applications.py backend/tests/test_applications_flow.py
git commit -m "feat: approve route with generation pipeline and conditional-update concurrency guard"
```

---

### Task 12: Run the server manually and smoke-test

**Files:** none (manual verification only)

- [ ] **Step 1: Start the API**

Run: `cd backend && uvicorn app.main:app --reload`
Expected: `Application startup complete.`

- [ ] **Step 2: Open API docs**

Visit `http://127.0.0.1:8000/docs` in a browser.
Expected: Swagger UI shows `applications` and `skills` route groups.

- [ ] **Step 3: Insert a manual API key for smoke testing**

Run:
```bash
docker exec -i $(docker compose ps -q db) psql -U postgres -d resume_orchestrator -c "
INSERT INTO api_keys (id, user_id, key_hash) VALUES (
  gen_random_uuid(), gen_random_uuid(),
  encode(sha256('dev-smoke-test-key'::bytea), 'hex')
);"
```
Note: this requires the `pgcrypto` extension for `gen_random_uuid()`. If it errors with "function gen_random_uuid() does not exist", run `CREATE EXTENSION IF NOT EXISTS pgcrypto;` first, then retry the insert.

- [ ] **Step 4: Exercise the full flow with curl**

```bash
curl -s -X POST http://127.0.0.1:8000/api/applications \
  -H "X-API-Key: dev-smoke-test-key" -H "Content-Type: application/json" \
  -d '{"company_name":"Acme","role_title":"Engineer","jd_text":"Need Python and SQL."}'
```
Expected: JSON response with `"status":"awaiting_human"`.

Take the `id` from the response and run:
```bash
curl -s -X POST http://127.0.0.1:8000/api/applications/<id>/approve \
  -H "X-API-Key: dev-smoke-test-key" -H "Content-Type: application/json" \
  -d '{"approved_skills":["Python","SQL"]}'
```
Expected: JSON response with `"status":"completed"` and a `final_resume_json.summary` ending in `(polished)`.

- [ ] **Step 5: Stop the server** (Ctrl+C) — no commit for this task, it's manual verification only.

---

## Self-Review Notes

- **Spec coverage:** auth/isolation (Task 6, enforced in every repo function from Task 7), conditional-UPDATE concurrency+idempotency guard (Task 7 + tested in Task 11), schema versioning columns (Task 2 migration — `extracted_skills_version`/`approved_skills_version` present in schema; deserialization branching on version is deferred since only v1 exists, consistent with spec's "V1 is the only version implemented now"), expanded status enum (Task 2), all 3 state-machine routes (Tasks 9–11), skills CRUD (Task 9), stub LLM clients (Task 5), required test cases — happy path/concurrent approve/cross-user 404/wrong-state 409/missing-invalid key 401 — all present (Tasks 9 & 11).
- **Type consistency:** `update_status_conditional(db, app_id, user_id, expected_status, next_status, **fields)` signature is identical everywhere it's called (Tasks 10, 11). `ApplicationOut`/`PendingApprovalOut`/`ApproveRequest` field names match between schema definitions (Task 4) and router usage (Tasks 10–11).
- **No placeholders:** every step has complete, runnable code.
