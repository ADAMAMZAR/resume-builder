import hashlib
import os
import pathlib
import uuid

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import get_db
from app.main import app
from app.models.api_key import ApiKey

load_dotenv(pathlib.Path(__file__).resolve().parents[1] / ".env")

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5433/resume_orchestrator_test",
)
MIGRATION_PATH = pathlib.Path(__file__).resolve().parents[2] / "migrations" / "001_init.sql"

test_engine = create_async_engine(TEST_DATABASE_URL)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


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
