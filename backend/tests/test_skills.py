async def test_create_and_list_skill(client, api_key):
    create_resp = await client.post(
        "/api/skills",
        json={
            "skill_name": "Python",
            "category": "hard_skill",
            "proficiency_level": "expert",
            "context": "5 years building backend services",
        },
        headers=api_key["headers"],
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["skill_name"] == "Python"
    assert created["category"] == "hard_skill"

    list_resp = await client.get("/api/skills", headers=api_key["headers"])
    assert list_resp.status_code == 200
    skills = list_resp.json()
    assert len(skills) == 1
    assert skills[0]["skill_name"] == "Python"


async def test_missing_api_key_returns_401(client):
    resp = await client.get("/api/skills")
    assert resp.status_code == 401


async def test_invalid_api_key_returns_401(client):
    resp = await client.get("/api/skills", headers={"X-API-Key": "not-a-real-key"})
    assert resp.status_code == 401
