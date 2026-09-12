"""Test fixtures.

The suite runs against a throwaway SQLite database so it needs no services.
Environment is set before any application module is imported, because the
engine and settings are created at import time.
"""

import os
import tempfile
from pathlib import Path

_TMP_DB = Path(tempfile.mkdtemp(prefix="eail-tests-")) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DB}"
os.environ["AI_PROVIDER"] = "stub"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["DEMO_PASSWORD"] = "demo1234"
os.environ["APP_ENV"] = "test"

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.core.enums import SystemRole  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models.governance import GovernancePolicy  # noqa: E402
from app.models.organization import Department, Organization  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.workflow import Workflow, WorkflowVersion  # noqa: E402
from app.services.governance.policy import DEFAULT_POLICIES  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def fresh_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db():
    async with SessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


@pytest_asyncio.fixture
async def org(db):
    organization = Organization(name="Acme Corp", slug="acme")
    db.add(organization)
    await db.flush()
    engineering = Department(organization_id=organization.id, name="Engineering", headcount=10)
    finance = Department(organization_id=organization.id, name="Finance", headcount=5)
    db.add_all([engineering, finance])
    for entry in DEFAULT_POLICIES:
        db.add(
            GovernancePolicy(
                key=entry["key"],
                name=entry["name"],
                description=entry["description"],
                risk_level=entry["risk_level"],
                enabled=True,
                blocking=entry["blocking"],
                config={},
            )
        )
    await db.commit()
    return {"organization": organization, "engineering": engineering, "finance": finance}


@pytest_asyncio.fixture
async def users(db, org):
    password = hash_password("demo1234")
    employee = User(
        email="employee@demo.com",
        name="Alex Rivera",
        hashed_password=password,
        department_id=org["engineering"].id,
        job_role="Developer",
        system_role=SystemRole.EMPLOYEE,
    )
    manager = User(
        email="manager@demo.com",
        name="Priya Nandakumar",
        hashed_password=password,
        department_id=org["engineering"].id,
        job_role="Manager",
        system_role=SystemRole.MANAGER,
    )
    admin = User(
        email="admin@demo.com",
        name="Dana Whitfield",
        hashed_password=password,
        department_id=org["finance"].id,
        job_role="Manager",
        system_role=SystemRole.ADMIN,
    )
    outsider = User(
        email="outsider@demo.com",
        name="Sam Fielding",
        hashed_password=password,
        department_id=org["finance"].id,
        job_role="Finance",
        system_role=SystemRole.EMPLOYEE,
    )
    db.add_all([employee, manager, admin, outsider])
    await db.commit()
    return {"employee": employee, "manager": manager, "admin": admin, "outsider": outsider}


@pytest_asyncio.fixture
async def workflows(db, users):
    """A low-risk INTERNAL workflow and a CONFIDENTIAL one, plus a prohibited one."""
    tests_wf = Workflow(
        slug="generate_unit_tests",
        name="Generate Unit Tests",
        description="Generate unit tests for submitted code.",
        department="Engineering",
        target_role="Developer",
        task_type="code",
        risk_level="LOW",
        status="ACTIVE",
        requires_human_review=False,
        allowed_data_classification="INTERNAL",
        expected_output_format="code",
        estimated_manual_minutes=20,
        estimated_assisted_minutes=5,
        input_schema=[{"name": "code", "label": "Code", "type": "code", "required": True}],
        guidance={},
        current_version=1,
    )
    prohibited_wf = Workflow(
        slug="auto_reject_applicant",
        name="Automatically Reject Applicant",
        description="Prohibited use case.",
        department="Human Resources",
        target_role="HR",
        task_type="decision",
        risk_level="PROHIBITED",
        status="DRAFT",
        requires_human_review=True,
        allowed_data_classification="PUBLIC",
        expected_output_format="text",
        estimated_manual_minutes=0,
        estimated_assisted_minutes=0,
        input_schema=[],
        guidance={},
        current_version=1,
    )
    db.add_all([tests_wf, prohibited_wf])
    await db.flush()

    db.add(
        WorkflowVersion(
            workflow_id=tests_wf.id,
            version=1,
            system_prompt="Write unit tests.",
            prompt_template="Code:\n$code",
            model="gpt-4.1-mini",
            temperature=0.2,
            evaluation_rubric={
                "weights": {
                    "relevance": 0.3,
                    "completeness": 0.25,
                    "format_compliance": 0.35,
                    "safety": 0.1,
                },
                "deterministic": {"expect_code": "python", "expect_test_concepts": True},
                "judge_dimensions": ["relevance", "completeness", "clarity"],
            },
            changelog="Initial version.",
            created_by=users["admin"].id,
            is_active=True,
        )
    )
    db.add(
        WorkflowVersion(
            workflow_id=prohibited_wf.id,
            version=1,
            system_prompt="Blocked.",
            prompt_template="$application",
            model="gpt-4.1-mini",
            temperature=0.0,
            evaluation_rubric={},
            changelog="Registered as prohibited.",
            created_by=users["admin"].id,
            is_active=True,
        )
    )
    await db.commit()
    return {"unit_tests": tests_wf, "prohibited": prohibited_wf}


async def login(client, email: str, password: str = "demo1234") -> str:
    response = await client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
