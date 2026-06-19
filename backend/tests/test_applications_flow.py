async def test_create_application_extracts_skills_and_awaits_human(client, api_key):
    resp = await client.post(
        "/api/applications",
        json={
            "company_name": "Acme Corp",
            "role_title": "Backend Engineer",
            "jd_text": "Looking for someone strong in Python and SQL.",
        },
        headers=api_key["headers"],
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "awaiting_human"
    assert "Python" in body["extracted_skills"]["hard_skills"]


async def test_pending_approval_returns_extracted_skills(client, api_key):
    create_resp = await client.post(
        "/api/applications",
        json={"company_name": "Acme", "role_title": "Engineer", "jd_text": "JD text"},
        headers=api_key["headers"],
    )
    app_id = create_resp.json()["id"]

    resp = await client.get(f"/api/applications/{app_id}/pending-approval", headers=api_key["headers"])
    assert resp.status_code == 200
    assert "hard_skills" in resp.json()["extracted_skills"]


async def test_pending_approval_for_other_users_application_returns_404(client, api_key, db_session):
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
        f"/api/applications/{app_id}/pending-approval",
        headers={"X-API-Key": other_raw_key},
    )
    assert resp.status_code == 404


async def test_approve_runs_generation_pipeline_to_completion(client, api_key):
    create_resp = await client.post(
        "/api/applications",
        json={"company_name": "Acme", "role_title": "Engineer", "jd_text": "JD text"},
        headers=api_key["headers"],
    )
    app_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/applications/{app_id}/approve",
        json={"approved_skills": ["Python", "SQL"]},
        headers=api_key["headers"],
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["final_resume_json"]["summary"].endswith("(polished)")
    assert body["final_cover_letter_md"].endswith("(polished)")


async def test_approve_on_already_completed_application_returns_409(client, api_key):
    create_resp = await client.post(
        "/api/applications",
        json={"company_name": "Acme", "role_title": "Engineer", "jd_text": "JD text"},
        headers=api_key["headers"],
    )
    app_id = create_resp.json()["id"]

    first = await client.post(
        f"/api/applications/{app_id}/approve",
        json={"approved_skills": []},
        headers=api_key["headers"],
    )
    assert first.status_code == 200

    second = await client.post(
        f"/api/applications/{app_id}/approve",
        json={"approved_skills": []},
        headers=api_key["headers"],
    )
    assert second.status_code == 409


async def test_approve_on_other_users_application_returns_404(client, api_key, db_session):
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

    resp = await client.post(
        f"/api/applications/{app_id}/approve",
        json={"approved_skills": []},
        headers={"X-API-Key": other_raw_key},
    )
    assert resp.status_code == 404


async def test_concurrent_approve_only_one_request_succeeds(client, api_key):
    import asyncio

    create_resp = await client.post(
        "/api/applications",
        json={"company_name": "Acme", "role_title": "Engineer", "jd_text": "JD text"},
        headers=api_key["headers"],
    )
    app_id = create_resp.json()["id"]

    results = await asyncio.gather(
        client.post(
            f"/api/applications/{app_id}/approve",
            json={"approved_skills": []},
            headers=api_key["headers"],
        ),
        client.post(
            f"/api/applications/{app_id}/approve",
            json={"approved_skills": []},
            headers=api_key["headers"],
        ),
    )
    statuses = sorted(r.status_code for r in results)
    assert statuses == [200, 409]


async def test_created_application_includes_created_at(client, api_key):
    resp = await client.post(
        "/api/applications",
        json={"company_name": "Acme", "role_title": "Engineer", "jd_text": "JD text"},
        headers=api_key["headers"],
    )
    assert resp.status_code == 201
    assert "created_at" in resp.json()
    assert resp.json()["created_at"] is not None
