CREATE TABLE api_keys (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL UNIQUE,
    key_hash TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE skills_inventory (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES api_keys(user_id),
    skill_name TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('hard_skill', 'soft_skill', 'tool')),
    proficiency_level TEXT,
    context TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_skills_inventory_user_id ON skills_inventory(user_id);

CREATE TABLE applications (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES api_keys(user_id),
    company_name TEXT NOT NULL,
    role_title TEXT NOT NULL,
    jd_text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending_extraction' CHECK (
        status IN (
            'pending_extraction',
            'extraction_failed',
            'awaiting_human',
            'generating',
            'generation_failed',
            'completed'
        )
    ),
    extracted_skills JSONB,
    extracted_skills_version SMALLINT NOT NULL DEFAULT 1,
    approved_skills JSONB,
    approved_skills_version SMALLINT NOT NULL DEFAULT 1,
    final_resume_json JSONB,
    final_cover_letter_md TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_applications_user_id ON applications(user_id);
