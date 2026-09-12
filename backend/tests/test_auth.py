import pytest

from tests.conftest import auth, login


async def test_login_returns_token_and_profile(client, users):
    response = await client.post(
        "/auth/login", json={"email": "employee@demo.com", "password": "demo1234"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "employee@demo.com"
    assert body["user"]["job_role"] == "Developer"
    assert body["user"]["department_name"] == "Engineering"


@pytest.mark.parametrize(
    "email,password",
    [
        ("employee@demo.com", "wrong-password"),
        ("nobody@demo.com", "demo1234"),
    ],
)
async def test_login_rejects_bad_credentials(client, users, email, password):
    response = await client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 401


async def test_me_requires_a_token(client, users):
    assert (await client.get("/auth/me")).status_code == 401
    assert (
        await client.get("/auth/me", headers={"Authorization": "Bearer not-a-token"})
    ).status_code == 401


async def test_me_returns_the_caller(client, users):
    token = await login(client, "manager@demo.com")
    response = await client.get("/auth/me", headers=auth(token))
    assert response.status_code == 200
    assert response.json()["system_role"] == "MANAGER"


async def test_employee_cannot_reach_admin_routes(client, users):
    token = await login(client, "employee@demo.com")
    response = await client.get("/admin/governance", headers=auth(token))
    assert response.status_code == 403


async def test_employee_cannot_reach_manager_analytics(client, users):
    token = await login(client, "employee@demo.com")
    assert (await client.get("/analytics/adoption", headers=auth(token))).status_code == 403
    # ...but can always see their own dashboard.
    assert (await client.get("/analytics/me", headers=auth(token))).status_code == 200
