from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import applications, skills

app = FastAPI(title="Resume Orchestrator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(skills.router)
app.include_router(applications.router)
