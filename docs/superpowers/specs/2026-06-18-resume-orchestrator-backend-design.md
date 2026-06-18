# Resume & Cover Letter Orchestrator — Backend Design

Date: 2026-06-18
Status: Approved

## Context

CLAUDE.md defines an MVP backend: FastAPI state machine over a Postgres/Supabase
database, with Gemini doing extraction/drafting and Claude doing a final polish
pass. Architecture review (caveman-mode critique) found four gaps before
implementation:

1. No `user_id` on `skills_inventory` / `applications` → no multi-tenant isolation.
2. No concurrency guard on state transitions → double-`/approve` race can
   double-fire LLM calls and corrupt status.
3. No ownership check on routes → IDOR risk (any guessable UUID readable).
4. JSONB columns (`extracted_skills`, `approved_skills`) have no schema version →
   future Pydantic model changes silently break old rows.

This spec folds fixes for all four into the initial implementation rather than
retrofitting them later.

## Stack

- **API:** FastAPI, async routes
- **DB access:** SQLAlchemy (async) + asyncpg
- **DB:** Postgres via docker-compose locally. Plain SQL migrations, no
  Supabase-specific features (e.g. no `auth.uid()`), so the connection string
  can point at a real Supabase Postgres instance later with zero schema changes.
- **Validation:** Pydantic v2, matching the models already specified in CLAUDE.md
  (`ExtractedSkills`, `WorkExperience`, `TailoredResumeSchema`)
- **LLM clients:** stub implementations behind an `LLMClient` interface —
  `GeminiStubClient` and `ClaudeStubClient` return canned/deterministic JSON.
  Swapping to real `google-generativeai` / `anthropic` SDK calls later means
  implementing the same interface, no router/service changes needed.

## Auth & Data Isolation

- New table `api_keys`: `id (UUID PK)`, `user_id (UUID, unique)`,
  `key_hash (text, unique)`, `created_at`.
- Client sends `X-API-Key` header. FastAPI dependency `get_current_user`
  hashes it (sha256), looks up `api_keys.key_hash`, returns `user_id`.
  Missing/unknown key → `401`.
- `skills_inventory.user_id` and `applications.user_id` are
  `UUID NOT NULL REFERENCES api_keys(user_id)`, indexed.
- **Hard rule:** every repository function takes `user_id` as a required
  parameter and includes `WHERE user_id = :user_id` in its query — including
  single-row lookups by `id`. A request for `applications/{id}` belonging to
  another user returns `404` (not `403`, to avoid confirming the id exists).
- No DB-level RLS in this pass (app-layer enforcement only, per design
  decision — DB user is a single service-role connection). RLS via session
  variables is a documented future option if a second DB-level defense is
  wanted.

## State Machine

Status enum (Postgres `CHECK` constraint, not a native enum type, to keep
migrations simple):

```
pending_extraction → extraction_failed
pending_extraction → awaiting_human
awaiting_human     → generating
generating         → generation_failed
generating         → completed
```

Every transition is a single conditional UPDATE:

```sql
UPDATE applications
SET status = :next_status, ...
WHERE id = :id AND user_id = :user_id AND status = :expected_prior_status
```

- `rowcount == 1` → transition succeeded, proceed.
- `rowcount == 0` → either the row doesn't belong to this user (404) or it's
  not in the expected prior state (409 Conflict, body explains current
  status). This single check is both the concurrency guard (two simultaneous
  `/approve` calls: only one wins the UPDATE) and the idempotency guard (a
  retried `/approve` finds status already advanced and 409s instead of
  re-running the LLM pipeline).

## Schema Versioning

`applications` gains:
- `extracted_skills_version SMALLINT NOT NULL DEFAULT 1`
- `approved_skills_version SMALLINT NOT NULL DEFAULT 1`

Deserialization code branches on the version column when reading JSONB back
into Pydantic models. V1 is the only version implemented now; the column
exists so a V2 model change doesn't require a backfill migration.

## Routes

1. `POST /api/applications` — create row (`status=pending_extraction`),
   call `GeminiStubClient.extract_skills(jd_text)`, diff against
   `skills_inventory` for this user, conditional UPDATE to `awaiting_human`
   (or `extraction_failed` on LLM error) storing `extracted_skills`.
2. `GET /api/applications/{id}/pending-approval` — 404 if not owned, returns
   `extracted_skills` only when `status == awaiting_human`, else 409 with
   current status.
3. `POST /api/applications/{id}/approve` — conditional UPDATE
   `awaiting_human → generating`, storing `approved_skills`. On success
   (and only on success), runs the draft → judge pipeline:
   `GeminiStubClient.draft_resume(...)` then `ClaudeStubClient.polish(...)`,
   then conditional UPDATE `generating → completed` storing
   `final_resume_json` / `final_cover_letter_md` (or `generation_failed`).
4. `GET/POST /api/skills` — CRUD on `skills_inventory`, user-scoped.

## Testing

pytest + httpx `AsyncClient` against a docker-compose test Postgres
(separate database, migrations applied in a fixture). Required cases:

- Happy path through all 4 states.
- Two concurrent `/approve` calls on the same id → exactly one `200`, one `409`.
- `/applications/{other_user_id}` → `404`.
- `/approve` called when status is `pending_extraction` (not yet
  `awaiting_human`) → `409`.
- Missing/invalid `X-API-Key` → `401`.

## Out of scope (explicitly deferred)

- Real Gemini/Claude API calls (stubs only, per decision).
- DB-level RLS / session-variable isolation.
- Supabase Auth / JWT.
- Frontend (React/Vite) — backend only this pass.
- Langfuse observability wiring.
