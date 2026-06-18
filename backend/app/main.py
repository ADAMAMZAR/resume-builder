from fastapi import FastAPI

from app.routers import skills

app = FastAPI(title="Resume Orchestrator")
app.include_router(skills.router)
