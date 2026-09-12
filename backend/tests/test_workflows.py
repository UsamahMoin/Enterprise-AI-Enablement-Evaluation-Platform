from tests.conftest import auth, login


async def test_list_workflows_returns_catalogue(client, workflows, users):
    token = await login(client, "employee@demo.com")
    response = await client.get("/workflows", headers=auth(token))
    assert response.status_code == 200
    slugs = {item["slug"] for item in response.json()}
    assert {"generate_unit_tests", "auto_reject_applicant"} <= slugs


async def test_recommended_filters_to_the_callers_role(client, workflows, users):
    token = await login(client, "employee@demo.com")  # Developer
    response = await client.get("/workflows?recommended=true", headers=auth(token))
    assert response.status_code == 200
    roles = {item["target_role"] for item in response.json()}
    assert roles == {"Developer"}


async def test_filters_by_department_and_risk(client, workflows, users):
    token = await login(client, "employee@demo.com")
    by_department = await client.get("/workflows?department=Engineering", headers=auth(token))
    assert {item["slug"] for item in by_department.json()} == {"generate_unit_tests"}

    by_risk = await client.get("/workflows?risk_level=PROHIBITED", headers=auth(token))
    assert {item["slug"] for item in by_risk.json()} == {"auto_reject_applicant"}


async def test_workflow_detail_includes_active_version_and_metadata(client, workflows, users):
    token = await login(client, "employee@demo.com")
    response = await client.get(f"/workflows/{workflows['unit_tests'].id}", headers=auth(token))
    assert response.status_code == 200
    body = response.json()
    assert body["active_version"]["version"] == 1
    assert body["risk_level"] == "LOW"
    assert body["allowed_data_classification"] == "INTERNAL"
    assert body["estimated_manual_minutes"] == 20


async def test_workflow_can_be_fetched_by_slug(client, workflows, users):
    token = await login(client, "employee@demo.com")
    response = await client.get("/workflows/generate_unit_tests", headers=auth(token))
    assert response.status_code == 200
    assert response.json()["id"] == workflows["unit_tests"].id


async def test_unknown_workflow_is_404(client, workflows, users):
    token = await login(client, "employee@demo.com")
    assert (await client.get("/workflows/nope", headers=auth(token))).status_code == 404


async def test_new_version_supersedes_without_overwriting(client, workflows, users):
    """The point of versioning: v1 must still exist after v2 is published."""
    token = await login(client, "admin@demo.com")
    workflow_id = workflows["unit_tests"].id

    response = await client.post(
        f"/workflows/{workflow_id}/versions",
        headers=auth(token),
        json={
            "system_prompt": "Write unit tests. Cover boundary and error cases.",
            "prompt_template": "Code:\n$code",
            "changelog": "Required boundary and error coverage.",
            "activate": True,
        },
    )
    assert response.status_code == 201
    assert response.json()["version"] == 2

    versions = (
        await client.get(f"/workflows/{workflow_id}/versions", headers=auth(token))
    ).json()
    assert [v["version"] for v in versions] == [1, 2]
    assert [v["is_active"] for v in versions] == [False, True]
    assert versions[0]["system_prompt"] == "Write unit tests."  # v1 untouched


async def test_only_admins_may_publish_versions(client, workflows, users):
    token = await login(client, "employee@demo.com")
    response = await client.post(
        f"/workflows/{workflows['unit_tests'].id}/versions",
        headers=auth(token),
        json={"system_prompt": "x", "prompt_template": "$code"},
    )
    assert response.status_code == 403
