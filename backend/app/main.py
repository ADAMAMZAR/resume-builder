from fastapi import FastAPI

from app.routers import applications, skills

app = FastAPI(title="Resume Orchestrator")
app.include_router(skills.router)
app.include_router(applications.router)
