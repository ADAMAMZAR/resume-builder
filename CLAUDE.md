# Project: AI-Driven Resume & Cover Letter Orchestrator (MVP)

## Context & Engineering Standards
You are acting as a Senior Staff Engineer assisting in building a highly scalable, maintainable, and observable backend system. 

The goal is to build an automated resume and cover letter generator tailored to specific job descriptions. 
Do not suggest over-engineered solutions. We are prioritizing "Business Impact" and "Minimum Viable Product" (MVP) principles. 
Security, data isolation, and state management are non-negotiable.

## System Architecture
*   **Frontend:** React (Vite) + Tailwind CSS (Handles UI and Human-in-the-Loop approval)
*   **Backend:** FastAPI (Python)
*   **Database:** Supabase (PostgreSQL) - Manages application state and user skills inventory
*   **Primary LLM:** Gemini 1.5 Flash API (Structured JSON extraction and initial drafting)
*   **Judge LLM:** Claude 3.5 Sonnet API (Final polish and critique)
*   **Observability:** Langfuse (or equivalent) for tracing LLM latency and token usage

## MVP Boundaries (Strictly Enforced)
1.  **No Web Scraping for V1:** The system will accept raw Job Description (JD) text pasted by the user. Do not implement Playwright or headless browsers.
2.  **Native Orchestration:** We are not using n8n or external workflow tools. FastAPI will manage the state machine natively using PostgreSQL to handle Human-in-the-Loop pauses.
3.  **Strict Output Schemas:** All LLM extraction must use Pydantic models and structured outputs.

## Database Schema Design (Supabase / PostgreSQL)

We need two primary tables to handle the state machine and data isolation.

**Table 1: `skills_inventory`**
Stores the user's base skills and experiences.
*   `id` (UUID, Primary Key)
*   `skill_name` (String)
*   `category` (String: hard_skill, soft_skill, tool)
*   `proficiency_level` (Integer or String)
*   `context` (Text: A brief description of how it was used, for the LLM to reference)

**Table 2: `applications`**
Acts as the State Machine tracker for each job application.
*   `id` (UUID, Primary Key)
*   `company_name` (String)
*   `role_title` (String)
*   `jd_text` (Text)
*   `status` (Enum: `pending_extraction`, `awaiting_human`, `generating`, `completed`, `failed`)
*   `extracted_skills` (JSONB: The skills Gemini found in the JD)
*   `approved_skills` (JSONB: The skills the user confirmed they possess)
*   `final_resume_json` (JSONB)
*   `final_cover_letter_md` (Text)
*   `created_at` (Timestamp)

## The State Machine Flow (FastAPI Routes)

Please implement the backend following these exact sequential states.

### State 1: Ingestion & Extraction (`POST /api/applications`)
*   Accepts `company_name`, `role_title`, and `jd_text`.
*   Creates a new record in `applications` with status `pending_extraction`.
*   Calls Gemini 1.5 Flash (using `response_mime_type="application/json"` and a Pydantic schema) to extract a list of required skills from the `jd_text`.
*   Compares extracted skills against `skills_inventory`.
*   Updates the `applications` record: saves the missing/unverified skills to `extracted_skills` and changes status to `awaiting_human`.

### State 2: Human-in-the-Loop (`GET /api/applications/{id}/pending-approval`)
*   Frontend polls this endpoint or uses Supabase real-time to detect the `awaiting_human` state.
*   Returns the `extracted_skills` that need human verification.

### State 3: Approval & Generation (`POST /api/applications/{id}/approve`)
*   Accepts the user's filtered list of skills (the ones they clicked "Yes" to).
*   Updates `applications.status` to `generating`.
*   Updates `applications.approved_skills`.
*   **Drafting Step:** Passes the base resume, `approved_skills`, and `jd_text` to Gemini 1.5 Flash to generate a highly tailored resume (as JSON) and a cover letter (as Markdown).
*   **The Judge Step:** Passes Gemini's output to Claude 3.5 Sonnet to rewrite awkward phrasing, eliminate repetitive verbs, and ensure high business impact language.
*   Updates `applications.status` to `completed` and saves the final outputs to the database.

## Pydantic Models for LLM Structured Output

```python
from pydantic import BaseModel
from typing import List

class ExtractedSkills(BaseModel):
    hard_skills: List[str]
    soft_skills: List[str]
    tools_and_frameworks: List[str]

class WorkExperience(BaseModel):
    company: str
    role: str
    impact_bullets: List[str]

class TailoredResumeSchema(BaseModel):
    summary: str
    skills_aligned: List[str]
    experience: List[WorkExperience]