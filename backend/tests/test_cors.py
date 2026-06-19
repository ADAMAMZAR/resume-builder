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
