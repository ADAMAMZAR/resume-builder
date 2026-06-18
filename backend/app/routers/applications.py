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
