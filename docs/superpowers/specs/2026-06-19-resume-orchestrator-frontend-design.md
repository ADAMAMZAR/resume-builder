# Resume Orchestrator Frontend — Design Spec

## Context

The backend (see `2026-06-18-resume-orchestrator-backend-design.md`) implements the full state machine from CLAUDE.md: skills inventory CRUD, application create/extract, human-in-the-loop skill approval, and AI generation (stub LLM clients). No frontend exists yet.

The user supplied 4 UI mockups for a product called "CareerDraft": (1) a Resume Architect input + analysis-results screen, (2) a drag-and-drop resume content editor with live preview, (3) a cover letter editor, (4) a templates/settings/branding screen. These mockups depict significantly more functionality than the backend supports (file upload, PDF/JSON export, template management, branding settings, structured drag-and-drop resume editing).

**Scope decision (confirmed with user):** build only the screens that map to real backend functionality, styled in the visual language of the mockups. Skip file upload, PDF/JSON export, template management, and the editable drag-and-drop resume builder — none of these have backend support and CLAUDE.md explicitly warns against over-engineering beyond MVP.

## Backend additions required

The existing backend has no way to re-fetch an application's state after creation/approval, and no way to list a user's applications. Both are needed for a normal browser experience (refresh, navigation). Confirmed with user to add these as small, additive backend changes:

1. **Map `created_at` on the `Application` ORM model** (`backend/app/models/application.py`). The column already exists in `migrations/001_init.sql`; it was deliberately left unmapped during backend work since nothing needed it. Add `created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)` (read-only — never written by application code, relies on the DB default).
2. **`GET /api/applications/{id}`** — new route in `backend/app/routers/applications.py`, reuses `applications_repo.get_application(db, user_id, app_id)`. 404 if missing or not owned (same IDOR-safe pattern as existing routes). Returns `ApplicationOut`.
3. **`GET /api/applications`** — new route, new repo function `applications_repo.list_applications(db, user_id)` that does `SELECT * FROM applications WHERE user_id = :user_id ORDER BY created_at DESC`. Returns `list[ApplicationOut]`.

No changes to existing routes, request/response shapes, or the state machine itself. No new migration needed (column already exists).

## Frontend stack

- React + Vite + Tailwind CSS, per CLAUDE.md's stack.
- React Router for client-side routes (`/skills`, `/applications`, `/applications/new`, `/applications/:id`, `/settings`) — chosen over a single-view app because browser back/forward and refresh need to work naturally across a multi-step flow.
- No global state management library. Each page fetches what it needs directly.
- Plain `fetch`-based API client, no SDK/codegen.

## API client

`frontend/src/api.js` — single module exporting:
- `apiFetch(path, options)`: reads the API key from `localStorage.getItem('apiKey')`, attaches it as `X-API-Key`, sets `Content-Type: application/json` for requests with a body, throws an `ApiError` (with `.status` and parsed `.detail`) on non-2xx responses.
- Thin wrapper functions per endpoint: `listSkills()`, `createSkill(data)`, `listApplications()`, `getApplication(id)`, `createApplication(data)`, `getPendingApproval(id)`, `approveApplication(id, approvedSkills)`.

No retry logic, no caching layer — matches MVP scope.

## Pages

### Settings (`/settings`)
Single text input for the API key, "Save" button writes to `localStorage`. Shows current saved state. This is the only "auth" surface — there is no signup/login endpoint; keys are provisioned directly in the DB out-of-band (as already true for backend testing).

### My Skills (`/skills`)
- Fetches `listSkills()` on mount, renders as a list/table (skill_name, category badge, proficiency, context).
- An "Add Skill" form (skill_name, category select: hard_skill/soft_skill/tool, proficiency_level, context textarea) posts via `createSkill` and prepends to the list on success.
- No edit/delete UI — backend has no PATCH/DELETE routes for skills, so none is offered.

### New Application (`/applications/new`, app's default route)
Mirrors mockup 1's "Resume Architect" input panel: company name, role title, and a JD textarea, plus a primary "Run AI Analysis" button. No resume file upload (no backend field for it — the stub LLM client ignores any base resume and always drafts from hardcoded data). On submit, calls `createApplication`, then navigates to `/applications/:id` using the returned id.

### Application Detail (`/applications/:id`)
Single page that branches on `status`:
- **`pending_extraction`** or **`generating`**: a "processing…" placeholder; polls `getApplication(id)` every 2s until status changes.
- **`awaiting_human`**: calls `getPendingApproval(id)` to get `extracted_skills` (`hard_skills`, `soft_skills`, `tools_and_frameworks`), renders each as a checkbox list grouped by category (mirrors mockup 1's "Key Skills" panel — pre-checked by default, user can uncheck). An "Approve & Generate" button posts the checked skill names via `approveApplication` and starts polling again.
- **`completed`**: renders `final_resume_json` (summary, skills_aligned tags, experience entries with impact bullets) and `final_cover_letter_md` (rendered as preformatted/markdown-lite text) read-only, in two panels echoing mockups 2/3's preview layout. No editing, no PDF/JSON export.
- **`extraction_failed`** / **`generation_failed`**: an error panel stating generation failed, with a note to try creating a new application (no retry endpoint exists).

### Applications List (`/applications`)
Cards/table from `listApplications()`: company, role, status badge, created date, linking to each detail page. Not present in the mockups, but necessary now that a list endpoint exists — otherwise completed applications would be unreachable after leaving the detail page.

## Visual style

Tailwind utility classes approximating the mockups' shared visual language: dark/black sidebar with a logo wordmark and nav items (Skills, Applications, New Application, Settings), black primary buttons with white text, light-gray content cards with rounded corners, uppercase tracked-out micro-labels for section headers (e.g. "EXTRACTED HEADER", "KEY SKILLS"). No dark-mode toggle, no theming system, no branding/font settings — that entire screen (mockup 4) is out of scope.

## Error handling

- Network/API errors surface as an inline red banner on the current page (no toast library).
- 401 (bad/missing API key) anywhere redirects to `/settings` with a message to set a valid key.
- 404 on application detail shows a simple "not found" state.
- 409 on approve (lost the race, or already past `awaiting_human`) re-fetches the application and re-renders based on its actual current status rather than showing a raw error.

## Testing

No frontend test runner is being introduced in this pass (none exists yet, and adding one is beyond this scope). Verification is a manual smoke test: start the backend (docker-compose Postgres + uvicorn) and the Vite dev server, walk through Settings → add a skill → create an application → approve → see completed resume/cover letter, confirm against the actual running backend rather than mocks.

## Explicitly out of scope (matches mockups but no backend support)

- Resume/file upload (PDF/DOCX parsing)
- PDF/JSON export, "Download PDF"
- Template management, multiple resume templates, branding/font/color settings
- Drag-and-drop resume content editor, inline AI "Optimize" actions
- LinkedIn sync, sharing
- Drafts/storage quota UI
