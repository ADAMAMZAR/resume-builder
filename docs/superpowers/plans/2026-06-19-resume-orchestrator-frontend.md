# Resume Orchestrator Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a React + Vite + Tailwind frontend for the resume orchestrator backend, covering Settings (API key), Skills Inventory, New Application, Application Detail (extraction review → approval → generated result), and an Applications list — plus the small backend additions (CORS, `created_at` mapping, `GET /api/applications/{id}`, `GET /api/applications`) needed to support it.

**Architecture:** FastAPI backend gets three small additive changes (CORS middleware, a mapped `created_at` column, two new read-only GET routes) with no changes to existing behavior. The frontend is a standalone Vite app in `frontend/` that talks to the backend over `fetch`, storing the API key in `localStorage` and using React Router for 5 pages. No global state library; each page fetches its own data.

**Tech Stack:** Backend: FastAPI, SQLAlchemy 2.0 async, pytest (existing stack, unchanged). Frontend: React 18, Vite 5, Tailwind CSS 3, React Router 6.

**Reference spec:** `docs/superpowers/specs/2026-06-19-resume-orchestrator-frontend-design.md`

---

## Backend additions

### Task 1: CORS middleware

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_cors.py` (new)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_cors.py`:

```python
async def test_cors_allows_frontend_dev_origin(client):
    resp = await client.options(
        "/api/skills",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `pytest tests/test_cors.py -v`
Expected: FAIL — response is 400 or missing the `access-control-allow-origin` header (no CORS middleware registered yet).

- [ ] **Step 3: Add CORS middleware**

Replace the full content of `backend/app/main.py` with:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cors.py -v`
Expected: PASS

- [ ] **Step 5: Run full backend test suite to confirm no regressions**

Run: `pytest -v`
Expected: all tests pass (previous count + 1)

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/tests/test_cors.py
git commit -m "feat: enable CORS for frontend dev server"
```

---

### Task 2: Map `created_at` on Application model, expose on ApplicationOut

**Files:**
- Modify: `backend/app/models/application.py`
- Modify: `backend/app/schemas/applications.py`
- Test: `backend/tests/test_applications_flow.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_applications_flow.py`:

```python
async def test_created_application_includes_created_at(client, api_key):
    resp = await client.post(
        "/api/applications",
        json={"company_name": "Acme", "role_title": "Engineer", "jd_text": "JD text"},
        headers=api_key["headers"],
    )
    assert resp.status_code == 201
    assert "created_at" in resp.json()
    assert resp.json()["created_at"] is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `pytest tests/test_applications_flow.py::test_created_application_includes_created_at -v`
Expected: FAIL — `KeyError` or `created_at` missing from response body (field doesn't exist on `ApplicationOut` yet).

- [ ] **Step 3: Map the column on the model**

In `backend/app/models/application.py`, add the import and column. Full file becomes:

```python
import uuid
from datetime import datetime

from sqlalchemy import SmallInteger, String, Text, TIMESTAMP
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
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
```

Note: this column is never written by application code — it relies entirely on the DB's `DEFAULT now()` from `migrations/001_init.sql:42`. After `INSERT`, `create_application`'s existing `await db.refresh(app_row)` call (in `backend/app/repositories/applications_repo.py:20`) already reloads it from the DB, so no repo changes are needed.

- [ ] **Step 4: Add the field to ApplicationOut**

In `backend/app/schemas/applications.py`, add the import and field. Update the `ApplicationOut` class to:

```python
import uuid
from datetime import datetime

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
    created_at: datetime

    model_config = {"from_attributes": True}


class PendingApprovalOut(BaseModel):
    id: uuid.UUID
    extracted_skills: dict


class ApproveRequest(BaseModel):
    approved_skills: list[str]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_applications_flow.py::test_created_application_includes_created_at -v`
Expected: PASS

- [ ] **Step 6: Run full backend test suite to confirm no regressions**

Run: `pytest -v`
Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/application.py backend/app/schemas/applications.py backend/tests/test_applications_flow.py
git commit -m "feat: expose created_at on applications"
```

---

### Task 3: `GET /api/applications/{id}` route

**Files:**
- Modify: `backend/app/routers/applications.py`
- Test: `backend/tests/test_applications_flow.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_applications_flow.py`:

```python
async def test_get_application_returns_current_state(client, api_key):
    create_resp = await client.post(
        "/api/applications",
        json={"company_name": "Acme", "role_title": "Engineer", "jd_text": "JD text"},
        headers=api_key["headers"],
    )
    app_id = create_resp.json()["id"]

    resp = await client.get(f"/api/applications/{app_id}", headers=api_key["headers"])
    assert resp.status_code == 200
    assert resp.json()["id"] == app_id
    assert resp.json()["status"] == "awaiting_human"


async def test_get_application_for_other_users_application_returns_404(client, api_key, db_session):
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
        f"/api/applications/{app_id}",
        headers={"X-API-Key": other_raw_key},
    )
    assert resp.status_code == 404


async def test_get_application_not_found_returns_404(client, api_key):
    import uuid

    resp = await client.get(f"/api/applications/{uuid.uuid4()}", headers=api_key["headers"])
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`): `pytest tests/test_applications_flow.py -k test_get_application -v`
Expected: FAIL — 404 Not Found for the route itself (no such route registered).

- [ ] **Step 3: Add the route**

In `backend/app/routers/applications.py`, add this route. Place it directly after the `create_application_route` function (before `pending_approval_route`), so the file reads:

```python
@router.get("/{app_id}", response_model=ApplicationOut)
async def get_application_route(
    app_id: uuid.UUID,
    user_id=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    app_row = await applications_repo.get_application(db, user_id, app_id)
    if app_row is None:
        raise HTTPException(status_code=404, detail="application not found")
    return app_row
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_applications_flow.py -k test_get_application -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run full backend test suite to confirm no regressions**

Run: `pytest -v`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/applications.py backend/tests/test_applications_flow.py
git commit -m "feat: add GET /api/applications/{id}"
```

---

### Task 4: `GET /api/applications` (list) route

**Files:**
- Modify: `backend/app/repositories/applications_repo.py`
- Modify: `backend/app/routers/applications.py`
- Test: `backend/tests/test_applications_flow.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_applications_flow.py`:

```python
async def test_list_applications_returns_only_own_apps_newest_first(client, api_key, db_session):
    import hashlib
    import uuid

    from app.models.api_key import ApiKey

    first = await client.post(
        "/api/applications",
        json={"company_name": "First Co", "role_title": "Engineer", "jd_text": "JD text"},
        headers=api_key["headers"],
    )
    second = await client.post(
        "/api/applications",
        json={"company_name": "Second Co", "role_title": "Engineer", "jd_text": "JD text"},
        headers=api_key["headers"],
    )

    other_user_id = uuid.uuid4()
    other_raw_key = f"other-key-{other_user_id}"
    other_hash = hashlib.sha256(other_raw_key.encode()).hexdigest()
    db_session.add(ApiKey(id=uuid.uuid4(), user_id=other_user_id, key_hash=other_hash))
    await db_session.commit()
    await client.post(
        "/api/applications",
        json={"company_name": "Other User Co", "role_title": "Engineer", "jd_text": "JD text"},
        headers={"X-API-Key": other_raw_key},
    )

    resp = await client.get("/api/applications", headers=api_key["headers"])
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert [a["company_name"] for a in body] == ["Second Co", "First Co"]
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `pytest tests/test_applications_flow.py::test_list_applications_returns_only_own_apps_newest_first -v`
Expected: FAIL — 404 Not Found (no such route registered).

- [ ] **Step 3: Add the repository function**

In `backend/app/repositories/applications_repo.py`, add this import and function. Add `desc` to the existing `sqlalchemy` import line, then add the function after `get_application`:

```python
from sqlalchemy import desc, select, update
```

```python
async def list_applications(db: AsyncSession, user_id: uuid.UUID) -> list[Application]:
    result = await db.execute(
        select(Application)
        .where(Application.user_id == user_id)
        .order_by(desc(Application.created_at))
    )
    return list(result.scalars().all())
```

- [ ] **Step 4: Add the route**

In `backend/app/routers/applications.py`, add this route directly after `gemini`/`claude` instantiation and before `create_application_route`:

```python
@router.get("", response_model=list[ApplicationOut])
async def list_applications_route(
    user_id=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await applications_repo.list_applications(db, user_id)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_applications_flow.py::test_list_applications_returns_only_own_apps_newest_first -v`
Expected: PASS

- [ ] **Step 6: Run full backend test suite to confirm no regressions**

Run: `pytest -v`
Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/repositories/applications_repo.py backend/app/routers/applications.py backend/tests/test_applications_flow.py
git commit -m "feat: add GET /api/applications list endpoint"
```

---

## Frontend

### Task 5: Scaffold the Vite + React + Tailwind project

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.jsx`
- Create: `frontend/src/index.css`
- Create: `frontend/src/App.jsx`
- Create: `frontend/.gitignore`
- Create: `frontend/.env.example`

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "resume-orchestrator-frontend",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.2"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.1",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.47",
    "tailwindcss": "^3.4.13",
    "vite": "^5.4.8"
  }
}
```

- [ ] **Step 2: Create `frontend/vite.config.js`**

```js
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
});
```

- [ ] **Step 3: Create `frontend/tailwind.config.js`**

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {},
  },
  plugins: [],
};
```

- [ ] **Step 4: Create `frontend/postcss.config.js`**

```js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 5: Create `frontend/index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>CareerDraft</title>
  </head>
  <body class="bg-gray-50">
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

- [ ] **Step 6: Create `frontend/src/index.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 7: Create `frontend/src/App.jsx`** (placeholder, replaced in Task 7)

```jsx
export default function App() {
  return <div className="p-8 text-xl">CareerDraft — loading routes...</div>;
}
```

- [ ] **Step 8: Create `frontend/src/main.jsx`**

```jsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 9: Create `frontend/.gitignore`**

```
node_modules/
dist/
.env
```

- [ ] **Step 10: Create `frontend/.env.example`**

```
VITE_API_BASE_URL=http://localhost:8000
```

- [ ] **Step 11: Install dependencies and verify the dev server boots**

Run: `cd frontend && npm install`
Expected: install completes with no errors.

Run: `npm run dev`
Expected: Vite prints a local URL (e.g. `http://localhost:5173/`). Open it in a browser and confirm the placeholder text "CareerDraft — loading routes..." renders. Stop the dev server (Ctrl+C) once confirmed.

- [ ] **Step 12: Commit**

```bash
git add frontend/package.json frontend/vite.config.js frontend/tailwind.config.js frontend/postcss.config.js frontend/index.html frontend/src/main.jsx frontend/src/index.css frontend/src/App.jsx frontend/.gitignore frontend/.env.example
git commit -m "feat: scaffold Vite + React + Tailwind frontend"
```

Note: `package-lock.json` and `node_modules/` — commit `package-lock.json` too (it's not gitignored) for reproducible installs:

```bash
git add frontend/package-lock.json
git commit -m "chore: add frontend package-lock.json" --allow-empty
```

(If `package-lock.json` was already included in the first commit because `git add` ran after `npm install`, skip this second commit — check with `git status` first.)

---

### Task 6: API client module

**Files:**
- Create: `frontend/src/api.js`

- [ ] **Step 1: Create `frontend/src/api.js`**

```js
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

export function getApiKey() {
  return localStorage.getItem("apiKey") || "";
}

export function setApiKey(key) {
  localStorage.setItem("apiKey", key);
}

async function apiFetch(path, options = {}) {
  const headers = {
    "X-API-Key": getApiKey(),
    ...options.headers,
  };
  if (options.body) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // response had no JSON body
    }
    if (response.status === 401 && window.location.pathname !== "/settings") {
      sessionStorage.setItem("authMessage", "Your API key is missing or invalid. Please set a valid key.");
      window.location.assign("/settings");
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) {
    return null;
  }
  return response.json();
}

export function listSkills() {
  return apiFetch("/api/skills");
}

export function createSkill(data) {
  return apiFetch("/api/skills", { method: "POST", body: JSON.stringify(data) });
}

export function listApplications() {
  return apiFetch("/api/applications");
}

export function getApplication(id) {
  return apiFetch(`/api/applications/${id}`);
}

export function createApplication(data) {
  return apiFetch("/api/applications", { method: "POST", body: JSON.stringify(data) });
}

export function getPendingApproval(id) {
  return apiFetch(`/api/applications/${id}/pending-approval`);
}

export function approveApplication(id, approvedSkills) {
  return apiFetch(`/api/applications/${id}/approve`, {
    method: "POST",
    body: JSON.stringify({ approved_skills: approvedSkills }),
  });
}
```

- [ ] **Step 2: Manual verification**

This module has no automated tests (per spec, no frontend test runner is introduced this pass). It will be exercised end-to-end in Task 13. Confirm visually it has no syntax errors:

Run: `cd frontend && npx vite build`
Expected: build fails only because pages don't exist yet importing from non-existent files is NOT happening yet (this module isn't imported by anything yet) — the build should succeed (App.jsx is still the Task 5 placeholder). If it fails, fix any syntax error in `api.js` before proceeding.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api.js
git commit -m "feat: add frontend API client"
```

---

### Task 7: App shell, routing, and Sidebar layout

**Files:**
- Create: `frontend/src/components/Sidebar.jsx`
- Create: `frontend/src/components/Layout.jsx`
- Create: `frontend/src/components/ErrorBanner.jsx`
- Modify: `frontend/src/App.jsx`
- Create: `frontend/src/pages/Settings.jsx` (placeholder, filled in Task 8)
- Create: `frontend/src/pages/Skills.jsx` (placeholder, filled in Task 9)
- Create: `frontend/src/pages/NewApplication.jsx` (placeholder, filled in Task 10)
- Create: `frontend/src/pages/ApplicationDetail.jsx` (placeholder, filled in Task 11)
- Create: `frontend/src/pages/ApplicationsList.jsx` (placeholder, filled in Task 12)

- [ ] **Step 1: Add react-router-dom (already in package.json from Task 5) — confirm it's installed**

Run: `cd frontend && npm ls react-router-dom`
Expected: prints the installed version (it was already in `package.json` dependencies from Task 5's `npm install`).

- [ ] **Step 2: Create `frontend/src/components/ErrorBanner.jsx`**

```jsx
export default function ErrorBanner({ message }) {
  if (!message) return null;
  return (
    <div className="mb-4 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800">
      {message}
    </div>
  );
}
```

- [ ] **Step 3: Create `frontend/src/components/Sidebar.jsx`**

```jsx
import { NavLink } from "react-router-dom";

const navItems = [
  { to: "/applications/new", label: "New Application" },
  { to: "/applications", label: "Applications" },
  { to: "/skills", label: "My Skills" },
  { to: "/settings", label: "Settings" },
];

function linkClasses({ isActive }) {
  return [
    "block rounded-lg px-4 py-2 text-sm font-medium",
    isActive ? "bg-white text-black" : "text-gray-300 hover:bg-gray-800",
  ].join(" ");
}

export default function Sidebar() {
  return (
    <aside className="flex h-screen w-60 flex-col bg-black px-4 py-6">
      <div className="mb-8 px-2 text-lg font-bold text-white">CareerDraft</div>
      <nav className="flex flex-col gap-1">
        {navItems.map((item) => (
          <NavLink key={item.to} to={item.to} className={linkClasses}>
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
```

- [ ] **Step 4: Create `frontend/src/components/Layout.jsx`**

```jsx
import Sidebar from "./Sidebar.jsx";

export default function Layout({ children }) {
  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-8">{children}</main>
    </div>
  );
}
```

- [ ] **Step 5: Create placeholder pages**

`frontend/src/pages/Settings.jsx`:

```jsx
export default function Settings() {
  return <div>Settings page (Task 8)</div>;
}
```

`frontend/src/pages/Skills.jsx`:

```jsx
export default function Skills() {
  return <div>Skills page (Task 9)</div>;
}
```

`frontend/src/pages/NewApplication.jsx`:

```jsx
export default function NewApplication() {
  return <div>New Application page (Task 10)</div>;
}
```

`frontend/src/pages/ApplicationDetail.jsx`:

```jsx
export default function ApplicationDetail() {
  return <div>Application Detail page (Task 11)</div>;
}
```

`frontend/src/pages/ApplicationsList.jsx`:

```jsx
export default function ApplicationsList() {
  return <div>Applications List page (Task 12)</div>;
}
```

- [ ] **Step 6: Replace `frontend/src/App.jsx` with routing**

```jsx
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import Settings from "./pages/Settings.jsx";
import Skills from "./pages/Skills.jsx";
import NewApplication from "./pages/NewApplication.jsx";
import ApplicationDetail from "./pages/ApplicationDetail.jsx";
import ApplicationsList from "./pages/ApplicationsList.jsx";

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Navigate to="/applications/new" replace />} />
          <Route path="/applications/new" element={<NewApplication />} />
          <Route path="/applications" element={<ApplicationsList />} />
          <Route path="/applications/:id" element={<ApplicationDetail />} />
          <Route path="/skills" element={<Skills />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
```

- [ ] **Step 7: Manual verification**

Run: `cd frontend && npm run dev`
Expected: open `http://localhost:5173/` in a browser — it redirects to `/applications/new` and shows the dark sidebar with 4 nav links plus "New Application page (Task 10)" in the main area. Click each nav link and confirm the corresponding placeholder text renders and the active link highlights white. Stop the dev server once confirmed.

- [ ] **Step 8: Commit**

```bash
git add frontend/src
git commit -m "feat: add app shell, routing, and sidebar layout"
```

---

### Task 8: Settings page (API key)

**Files:**
- Modify: `frontend/src/pages/Settings.jsx`

- [ ] **Step 1: Replace `frontend/src/pages/Settings.jsx`**

```jsx
import { useEffect, useState } from "react";
import { getApiKey, setApiKey } from "../api.js";

export default function Settings() {
  const [key, setKey] = useState(getApiKey());
  const [saved, setSaved] = useState(false);
  const [authMessage, setAuthMessage] = useState("");

  useEffect(() => {
    const message = sessionStorage.getItem("authMessage");
    if (message) {
      setAuthMessage(message);
      sessionStorage.removeItem("authMessage");
    }
  }, []);

  function handleSave(e) {
    e.preventDefault();
    setApiKey(key.trim());
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <div className="max-w-md">
      <h1 className="mb-2 text-3xl font-bold">Settings</h1>
      {authMessage && (
        <div className="mb-4 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800">
          {authMessage}
        </div>
      )}
      <p className="mb-6 text-gray-600">
        Paste the API key issued to you. It's stored only in this browser and sent as the
        <code className="mx-1 rounded bg-gray-200 px-1">X-API-Key</code> header on every request.
      </p>
      <form onSubmit={handleSave} className="rounded-xl border border-gray-200 bg-white p-6">
        <label htmlFor="apiKey" className="mb-2 block text-xs font-semibold uppercase tracking-wide text-gray-500">
          API Key
        </label>
        <input
          id="apiKey"
          type="text"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          className="mb-4 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
          placeholder="paste your API key"
        />
        <button type="submit" className="rounded-lg bg-black px-4 py-2 text-sm font-medium text-white">
          Save
        </button>
        {saved && <span className="ml-3 text-sm text-green-600">Saved</span>}
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Manual verification**

Run: `cd frontend && npm run dev`. Navigate to `/settings`, type a value into the field, click Save, confirm "Saved" appears. Reload the page and confirm the field still shows the saved value (proves `localStorage` persistence). Open browser devtools → Application → Local Storage and confirm an `apiKey` entry exists. Then navigate to `/skills` with an invalid key saved and confirm the app auto-redirects back to `/settings` showing the red "Your API key is missing or invalid" banner (this exercises the 401-redirect logic added in Task 6's `api.js`). Stop the dev server once confirmed.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Settings.jsx
git commit -m "feat: add settings page for API key"
```

---

### Task 9: My Skills page

**Files:**
- Modify: `frontend/src/pages/Skills.jsx`

- [ ] **Step 1: Replace `frontend/src/pages/Skills.jsx`**

```jsx
import { useEffect, useState } from "react";
import { listSkills, createSkill, ApiError } from "../api.js";
import ErrorBanner from "../components/ErrorBanner.jsx";

const CATEGORY_LABELS = {
  hard_skill: "Hard Skill",
  soft_skill: "Soft Skill",
  tool: "Tool",
};

const emptyForm = { skill_name: "", category: "hard_skill", proficiency_level: "", context: "" };

export default function Skills() {
  const [skills, setSkills] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listSkills()
      .then(setSkills)
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Failed to load skills"))
      .finally(() => setLoading(false));
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    try {
      const created = await createSkill({
        ...form,
        proficiency_level: form.proficiency_level || null,
        context: form.context || null,
      });
      setSkills((prev) => [created, ...prev]);
      setForm(emptyForm);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to add skill");
    }
  }

  return (
    <div className="max-w-3xl">
      <h1 className="mb-6 text-3xl font-bold">My Skills</h1>
      <ErrorBanner message={error} />

      <form onSubmit={handleSubmit} className="mb-8 rounded-xl border border-gray-200 bg-white p-6">
        <h2 className="mb-4 text-xs font-semibold uppercase tracking-wide text-gray-500">Add Skill</h2>
        <div className="mb-3 grid grid-cols-2 gap-3">
          <input
            required
            placeholder="Skill name"
            value={form.skill_name}
            onChange={(e) => setForm({ ...form, skill_name: e.target.value })}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
          <select
            value={form.category}
            onChange={(e) => setForm({ ...form, category: e.target.value })}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          >
            {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <input
            placeholder="Proficiency level (optional)"
            value={form.proficiency_level}
            onChange={(e) => setForm({ ...form, proficiency_level: e.target.value })}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
        </div>
        <textarea
          placeholder="Context (optional) — how you used this skill"
          value={form.context}
          onChange={(e) => setForm({ ...form, context: e.target.value })}
          className="mb-4 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
          rows={2}
        />
        <button type="submit" className="rounded-lg bg-black px-4 py-2 text-sm font-medium text-white">
          Add Skill
        </button>
      </form>

      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : skills.length === 0 ? (
        <p className="text-gray-500">No skills yet. Add your first one above.</p>
      ) : (
        <ul className="space-y-2">
          {skills.map((skill) => (
            <li key={skill.id} className="rounded-xl border border-gray-200 bg-white p-4">
              <div className="flex items-center gap-2">
                <span className="font-medium">{skill.skill_name}</span>
                <span className="rounded-full bg-gray-200 px-2 py-0.5 text-xs">
                  {CATEGORY_LABELS[skill.category] || skill.category}
                </span>
                {skill.proficiency_level && (
                  <span className="text-xs text-gray-500">{skill.proficiency_level}</span>
                )}
              </div>
              {skill.context && <p className="mt-1 text-sm text-gray-600">{skill.context}</p>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Manual verification**

Prerequisite: backend running (`cd backend && uvicorn app.main:app --reload`) against the docker-compose Postgres, and a valid API key saved on `/settings` (insert one directly in the DB the same way backend tests do, or reuse a key created previously — see `docs/superpowers/plans/2026-06-18-resume-orchestrator-backend.md` Task 12 for the manual-smoke-test curl/SQL pattern).

Run: `cd frontend && npm run dev`. Navigate to `/skills`. Add a skill via the form, confirm it appears at the top of the list immediately. Reload the page and confirm it persists (fetched from the backend). Try submitting with an invalid/missing API key (clear it on `/settings`) and confirm the red error banner appears instead of a crash. Stop the dev server once confirmed.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Skills.jsx
git commit -m "feat: add my skills page"
```

---

### Task 10: New Application page

**Files:**
- Modify: `frontend/src/pages/NewApplication.jsx`

- [ ] **Step 1: Replace `frontend/src/pages/NewApplication.jsx`**

```jsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createApplication, ApiError } from "../api.js";
import ErrorBanner from "../components/ErrorBanner.jsx";

export default function NewApplication() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ company_name: "", role_title: "", jd_text: "" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const created = await createApplication(form);
      navigate(`/applications/${created.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to create application");
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <h1 className="mb-2 text-3xl font-bold">Resume Architect</h1>
      <p className="mb-6 text-gray-600">
        Paste your target job description to begin the AI alignment.
      </p>
      <ErrorBanner message={error} />
      <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-gray-200 bg-white p-6">
        <div>
          <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-gray-500">
            Company Name
          </label>
          <input
            required
            value={form.company_name}
            onChange={(e) => setForm({ ...form, company_name: e.target.value })}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-gray-500">
            Role Title
          </label>
          <input
            required
            value={form.role_title}
            onChange={(e) => setForm({ ...form, role_title: e.target.value })}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-gray-500">
            Job Description
          </label>
          <textarea
            required
            rows={8}
            value={form.jd_text}
            onChange={(e) => setForm({ ...form, jd_text: e.target.value })}
            placeholder="Paste the target job description here..."
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
        </div>
        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-lg bg-black px-4 py-3 text-sm font-medium text-white disabled:opacity-50"
        >
          {submitting ? "Analyzing..." : "Run AI Analysis"}
        </button>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Manual verification**

Run: `cd frontend && npm run dev`. With backend running and an API key set, navigate to `/applications/new`, fill in all 3 fields, submit. Confirm the button shows "Analyzing..." briefly, then the browser navigates to `/applications/<some-id>` (showing the Task 11 placeholder text with that id implicitly working, since routing already handles `:id`). Stop the dev server once confirmed.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/NewApplication.jsx
git commit -m "feat: add new application page"
```

---

### Task 11: Application Detail page

**Files:**
- Modify: `frontend/src/pages/ApplicationDetail.jsx`

- [ ] **Step 1: Replace `frontend/src/pages/ApplicationDetail.jsx`**

```jsx
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import {
  getApplication,
  getPendingApproval,
  approveApplication,
  ApiError,
} from "../api.js";
import ErrorBanner from "../components/ErrorBanner.jsx";

const POLL_INTERVAL_MS = 2000;
const TERMINAL_STATUSES = ["awaiting_human", "completed", "extraction_failed", "generation_failed"];

export default function ApplicationDetail() {
  const { id } = useParams();
  const [application, setApplication] = useState(null);
  const [pendingSkills, setPendingSkills] = useState(null);
  const [checked, setChecked] = useState({});
  const [error, setError] = useState("");
  const [notFound, setNotFound] = useState(false);
  const [approving, setApproving] = useState(false);
  const pollRef = useRef(null);

  const fetchApplication = useCallback(async () => {
    try {
      const app = await getApplication(id);
      setApplication(app);
      setNotFound(false);
      return app;
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setNotFound(true);
      } else {
        setError(err instanceof ApiError ? err.detail : "Failed to load application");
      }
      return null;
    }
  }, [id]);

  useEffect(() => {
    let cancelled = false;

    async function tick() {
      const app = await fetchApplication();
      if (cancelled || !app) return;
      if (!TERMINAL_STATUSES.includes(app.status)) {
        pollRef.current = setTimeout(tick, POLL_INTERVAL_MS);
      }
    }

    tick();
    return () => {
      cancelled = true;
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, [fetchApplication]);

  useEffect(() => {
    if (application?.status !== "awaiting_human") {
      setPendingSkills(null);
      return;
    }
    getPendingApproval(id)
      .then((data) => {
        setPendingSkills(data.extracted_skills);
        const initial = {};
        for (const category of Object.values(data.extracted_skills)) {
          for (const skill of category) initial[skill] = true;
        }
        setChecked(initial);
      })
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Failed to load pending skills"));
  }, [application?.status, id]);

  async function handleApprove() {
    setApproving(true);
    setError("");
    const approvedSkills = Object.entries(checked)
      .filter(([, isChecked]) => isChecked)
      .map(([name]) => name);
    try {
      const updated = await approveApplication(id, approvedSkills);
      setApplication(updated);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        await fetchApplication();
      } else {
        setError(err instanceof ApiError ? err.detail : "Failed to approve application");
      }
    } finally {
      setApproving(false);
    }
  }

  if (notFound) {
    return <p className="text-gray-500">Application not found.</p>;
  }

  if (!application) {
    return <p className="text-gray-500">Loading...</p>;
  }

  return (
    <div className="max-w-3xl">
      <h1 className="mb-1 text-3xl font-bold">{application.role_title}</h1>
      <p className="mb-6 text-gray-600">{application.company_name}</p>
      <ErrorBanner message={error} />

      {(application.status === "pending_extraction" || application.status === "generating") && (
        <div className="rounded-xl border border-gray-200 bg-white p-6 text-gray-600">
          {application.status === "pending_extraction" ? "Extracting required skills..." : "Generating your tailored resume..."}
        </div>
      )}

      {(application.status === "extraction_failed" || application.status === "generation_failed") && (
        <div className="rounded-xl border border-red-300 bg-red-50 p-6 text-red-800">
          {application.status === "extraction_failed"
            ? "Skill extraction failed. Please create a new application."
            : "Resume generation failed. Please create a new application."}
        </div>
      )}

      {application.status === "awaiting_human" && pendingSkills && (
        <div className="rounded-xl border border-gray-200 bg-white p-6">
          <h2 className="mb-4 text-xs font-semibold uppercase tracking-wide text-gray-500">Key Skills</h2>
          {Object.entries(pendingSkills).map(([category, skillList]) => (
            <div key={category} className="mb-4">
              <h3 className="mb-2 text-sm font-medium capitalize">{category.replaceAll("_", " ")}</h3>
              <div className="flex flex-wrap gap-2">
                {skillList.map((skill) => (
                  <label
                    key={skill}
                    className="flex items-center gap-2 rounded-full border border-gray-300 px-3 py-1 text-sm"
                  >
                    <input
                      type="checkbox"
                      checked={!!checked[skill]}
                      onChange={(e) => setChecked({ ...checked, [skill]: e.target.checked })}
                    />
                    {skill}
                  </label>
                ))}
              </div>
            </div>
          ))}
          <button
            onClick={handleApprove}
            disabled={approving}
            className="mt-2 rounded-lg bg-black px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {approving ? "Generating..." : "Approve & Generate"}
          </button>
        </div>
      )}

      {application.status === "completed" && application.final_resume_json && (
        <div className="space-y-6">
          <div className="rounded-xl border border-gray-200 bg-white p-6">
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Summary</h2>
            <p className="mb-4 text-sm">{application.final_resume_json.summary}</p>
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Skills</h2>
            <div className="mb-4 flex flex-wrap gap-2">
              {application.final_resume_json.skills_aligned.map((skill) => (
                <span key={skill} className="rounded-full bg-gray-200 px-2 py-0.5 text-xs">
                  {skill}
                </span>
              ))}
            </div>
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Experience</h2>
            <div className="space-y-3">
              {application.final_resume_json.experience.map((exp, idx) => (
                <div key={idx}>
                  <p className="text-sm font-medium">
                    {exp.role} — {exp.company}
                  </p>
                  <ul className="ml-5 list-disc text-sm text-gray-600">
                    {exp.impact_bullets.map((bullet, bIdx) => (
                      <li key={bIdx}>{bullet}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-xl border border-gray-200 bg-white p-6">
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Cover Letter</h2>
            <pre className="whitespace-pre-wrap text-sm">{application.final_cover_letter_md}</pre>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Manual verification**

Run: `cd frontend && npm run dev`. With backend running and an API key set, create a new application (Task 10 flow). Confirm the detail page briefly shows "Extracting required skills..." then renders the Key Skills checkboxes grouped by category (hard_skills, soft_skills, tools_and_frameworks), all pre-checked. Uncheck one, click "Approve & Generate", confirm it shows "Generating..." then renders the completed Summary/Skills/Experience/Cover Letter panels. Reload the page on a completed application's URL and confirm it loads directly into the completed view (proves `GET /api/applications/{id}` round-trips correctly). Stop the dev server once confirmed.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ApplicationDetail.jsx
git commit -m "feat: add application detail page with approval flow"
```

---

### Task 12: Applications List page

**Files:**
- Modify: `frontend/src/pages/ApplicationsList.jsx`

- [ ] **Step 1: Replace `frontend/src/pages/ApplicationsList.jsx`**

```jsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listApplications, ApiError } from "../api.js";
import ErrorBanner from "../components/ErrorBanner.jsx";

const STATUS_LABELS = {
  pending_extraction: "Extracting",
  extraction_failed: "Extraction Failed",
  awaiting_human: "Awaiting Review",
  generating: "Generating",
  generation_failed: "Generation Failed",
  completed: "Completed",
};

function statusBadgeClasses(status) {
  if (status === "completed") return "bg-green-100 text-green-800";
  if (status.endsWith("failed")) return "bg-red-100 text-red-800";
  return "bg-gray-200 text-gray-800";
}

export default function ApplicationsList() {
  const [applications, setApplications] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listApplications()
      .then(setApplications)
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Failed to load applications"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-3xl">
      <h1 className="mb-6 text-3xl font-bold">Applications</h1>
      <ErrorBanner message={error} />
      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : applications.length === 0 ? (
        <p className="text-gray-500">
          No applications yet. <Link to="/applications/new" className="underline">Create one</Link>.
        </p>
      ) : (
        <ul className="space-y-2">
          {applications.map((app) => (
            <li key={app.id}>
              <Link
                to={`/applications/${app.id}`}
                className="flex items-center justify-between rounded-xl border border-gray-200 bg-white p-4 hover:border-gray-400"
              >
                <div>
                  <p className="font-medium">{app.role_title}</p>
                  <p className="text-sm text-gray-600">{app.company_name}</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-gray-500">
                    {new Date(app.created_at).toLocaleDateString()}
                  </span>
                  <span className={`rounded-full px-2 py-0.5 text-xs ${statusBadgeClasses(app.status)}`}>
                    {STATUS_LABELS[app.status] || app.status}
                  </span>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Manual verification**

Run: `cd frontend && npm run dev`. Navigate to `/applications` after creating at least one application. Confirm each application shows role/company/date/status badge, newest first, and clicking one navigates to its detail page. With zero applications (use a fresh API key with none created), confirm the "No applications yet" empty state with a working link to `/applications/new`. Stop the dev server once confirmed.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ApplicationsList.jsx
git commit -m "feat: add applications list page"
```

---

### Task 13: End-to-end smoke test and final review

**Files:** none (verification only)

- [ ] **Step 1: Start the full stack**

Run (from repo root): `docker compose up -d db` (ensure Postgres is up on port 5433).
Run (from `backend/`): `uvicorn app.main:app --reload` (port 8000).
Run (from `frontend/`): `npm run dev` (port 5173).

- [ ] **Step 2: Provision a fresh API key directly in the DB**

Connect to the DB (e.g. `docker compose exec db psql -U postgres -d resume_orchestrator`) and insert a row, following the same pattern used for backend's Task 12 manual smoke test:

```sql
INSERT INTO api_keys (id, user_id, key_hash)
VALUES (gen_random_uuid(), gen_random_uuid(), encode(sha256('smoke-test-key'::bytea), 'hex'));
```

(If `gen_random_uuid()`/`sha256` aren't available as SQL functions in this Postgres image, instead start a Python shell with the backend's venv active and run `import hashlib, uuid; uid = uuid.uuid4(); print(uid, hashlib.sha256(f"smoke-test-key".encode()).hexdigest())`, then insert those literal values via `INSERT INTO api_keys (id, user_id, key_hash) VALUES (gen_random_uuid(), '<uid>', '<hash>');`.)

- [ ] **Step 3: Walk the full user journey in a browser**

1. Open `http://localhost:5173/settings`, paste `smoke-test-key`, save.
2. Go to `/skills`, add one skill (e.g. "Python", hard_skill).
3. Go to `/applications/new`, fill in company/role/JD text, submit.
4. On the detail page, wait for the Key Skills checkboxes to appear, leave them checked, click "Approve & Generate".
5. Confirm the completed Summary/Skills/Experience/Cover Letter panels render with "(polished)" suffixes (proving the full create → extract → approve → generate → polish pipeline ran).
6. Go to `/applications`, confirm the new application appears with status "Completed".
7. Reload the detail page directly via URL and confirm it still renders the completed view (proves `GET /{id}` works after a hard refresh).

- [ ] **Step 4: Fix any issues found, committing fixes with descriptive messages**

If any step in Step 3 fails, fix the root cause in the relevant file from Tasks 1–12, re-run the affected step, and commit the fix separately (do not silently patch without a commit).

- [ ] **Step 5: Run the full backend test suite one final time**

Run (from `backend/`): `pytest -v`
Expected: all tests pass (no regressions from any Task 1-4 backend change).

- [ ] **Step 6: Final commit**

```bash
git add -A
git status
```

Review `git status` — if anything is unexpectedly unstaged or untracked (e.g. a forgotten file), investigate before committing. If everything is already committed from prior tasks (expected, since each task commits its own work), this step requires no further action.
