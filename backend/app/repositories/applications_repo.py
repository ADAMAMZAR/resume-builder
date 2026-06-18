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
