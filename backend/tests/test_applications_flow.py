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
