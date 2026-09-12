"""Seed the demo organisation.

Run with:  python -m app.seed  [--force]

Produces a populated "Acme Corp": six departments, 150 employees, the workflow
catalogue with its prompt version history, and roughly 1,500 historical
executions with evaluation scores and human feedback.

Every value is synthetic. The dataset is generated from fixed distributions
with a fixed random seed, so the dashboards are reproducible and the numbers
tell a deliberate story: Engineering has adopted, HR has not; the Finance
variance workflow scores below the attention threshold; and each prompt
version of the flagship workflows scores better than the one before it.
"""

import argparse
import asyncio
import json
import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.enums import ExecutionStatus, FeedbackDecision, SystemRole, ViolationType
from app.core.paths import SEED_DIR
from app.core.security import hash_password
from app.models.execution import EvaluationResult, Execution, HumanFeedback
from app.models.governance import GovernancePolicy, PolicyViolation
from app.models.organization import Department, Organization
from app.models.training import TrainingCompletion, TrainingModule
from app.models.user import User
from app.models.workflow import Workflow, WorkflowVersion
from app.services.ai.pricing import estimate_cost
from app.services.governance.policy import DEFAULT_POLICIES

RANDOM_SEED = 20260912
TOTAL_EMPLOYEES = 150
HISTORY_DAYS = 90
TARGET_EXECUTIONS = 1500

# Share of each department that has ever used the platform. The spread is the
# point of the demo: it is what an enablement lead would act on.
DEPARTMENT_ADOPTION = {
    "Engineering": 0.94,
    "Marketing": 0.83,
    "Customer Support": 0.80,
    "Operations": 0.77,
    "Finance": 0.55,
    "Human Resources": 0.47,
}

# (mean quality, standard deviation) for the *latest* prompt version.
WORKFLOW_QUALITY = {
    "generate_unit_tests": (92.0, 4.5),
    "explain_code": (90.0, 5.0),
    "review_code_defects": (86.0, 6.0),
    "meeting_notes_to_action_items": (93.0, 4.0),
    "summarize_meeting_notes": (91.0, 4.5),
    "draft_customer_response": (89.0, 5.5),
    "categorize_support_ticket": (94.0, 3.5),
    "improve_job_description": (84.0, 7.0),
    "summarize_interview_notes": (85.0, 6.5),
    "generate_campaign_variants": (86.0, 6.5),
    "analyze_customer_feedback": (88.0, 5.5),
    "explain_variance_report": (79.0, 8.0),
    "summarize_financial_narrative": (82.0, 7.0),
}

# Relative execution volume, so "most used workflows" is not uniform noise.
WORKFLOW_WEIGHT = {
    "summarize_meeting_notes": 14,
    "meeting_notes_to_action_items": 13,
    "generate_unit_tests": 12,
    "draft_customer_response": 12,
    "categorize_support_ticket": 10,
    "explain_code": 9,
    "generate_campaign_variants": 7,
    "analyze_customer_feedback": 6,
    "review_code_defects": 6,
    "improve_job_description": 4,
    "summarize_interview_notes": 3,
    "explain_variance_report": 3,
    "summarize_financial_narrative": 2,
}

# Earlier prompt versions scored worse. This is what makes the version
# comparison view show a real improvement rather than a flat line.
VERSION_PENALTY = {1: -15.0, 2: -7.0, 3: 0.0}

MODEL_BY_WORKFLOW_DEFAULT = "gpt-4.1-mini"

# Share of adopters by usage pattern. Lapsed users ran the platform early in
# the window and stopped; trialists ran it once or twice and never built a
# habit. Both are invisible if you only count total prompts.
LAPSED_SHARE = 0.11
TRIALIST_SHARE = 0.20
REGULAR_SHARE = 0.45
LAPSED_MIN_AGE_DAYS = 38

SAMPLE_OUTPUT_NOTE = (
    "[Seeded historical execution. Output text is not stored for synthetic "
    "history; scores, tokens, latency and cost are.]"
)


def load_json(name: str) -> dict | list:
    return json.loads((SEED_DIR / name).read_text())


async def already_seeded(db: AsyncSession) -> bool:
    count = (await db.execute(select(func.count(Organization.id)))).scalar_one()
    return count > 0


async def wipe(db: AsyncSession) -> None:
    for model in (
        HumanFeedback,
        EvaluationResult,
        Execution,
        PolicyViolation,
        TrainingCompletion,
        TrainingModule,
        WorkflowVersion,
        Workflow,
        GovernancePolicy,
        User,
        Department,
        Organization,
    ):
        await db.execute(delete(model))
    await db.commit()


async def seed_organisation(db: AsyncSession, rng: random.Random) -> dict:
    data = load_json("users.json")

    org = Organization(name=data["organization"]["name"], slug=data["organization"]["slug"])
    db.add(org)
    await db.flush()

    departments: dict[str, Department] = {}
    for entry in data["departments"]:
        department = Department(
            organization_id=org.id, name=entry["name"], headcount=entry["headcount"]
        )
        db.add(department)
        departments[entry["name"]] = department
    await db.flush()

    password = hash_password(settings.demo_password)
    users: list[User] = []

    for account in data["demo_accounts"]:
        user = User(
            email=account["email"],
            name=account["name"],
            hashed_password=password,
            department_id=departments[account["department"]].id,
            job_role=account["job_role"],
            system_role=account["system_role"],
        )
        db.add(user)
        users.append(user)

    # Fill each department up to its headcount with synthetic employees.
    taken_emails = {account["email"] for account in data["demo_accounts"]}
    for entry in data["departments"]:
        department = departments[entry["name"]]
        existing = sum(1 for u in users if u.department_id == department.id)
        for _ in range(entry["headcount"] - existing):
            given = rng.choice(data["given_names"])
            family = rng.choice(data["family_names"])
            base = f"{given.lower()}.{family.lower()}"
            email = f"{base}@acme-demo.test"
            suffix = 2
            while email in taken_emails:
                email = f"{base}{suffix}@acme-demo.test"
                suffix += 1
            taken_emails.add(email)

            job_role = rng.choice(entry["roles"])
            system_role = SystemRole.MANAGER if rng.random() < 0.08 else SystemRole.EMPLOYEE
            user = User(
                email=email,
                name=f"{given} {family}",
                hashed_password=password,
                department_id=department.id,
                job_role=job_role,
                system_role=system_role,
            )
            db.add(user)
            users.append(user)

    await db.flush()
    return {"organization": org, "departments": departments, "users": users}


async def seed_workflows(db: AsyncSession, admin: User) -> dict[str, Workflow]:
    data = load_json("workflows.json")
    workflows: dict[str, Workflow] = {}

    for entry in data:
        workflow = Workflow(
            slug=entry["slug"],
            name=entry["name"],
            description=entry["description"],
            department=entry["department"],
            target_role=entry["target_role"],
            task_type=entry["task_type"],
            risk_level=entry["risk_level"],
            status=entry["status"],
            requires_human_review=entry["requires_human_review"],
            allowed_data_classification=entry["allowed_data_classification"],
            expected_output_format=entry["expected_output_format"],
            estimated_manual_minutes=entry["estimated_manual_minutes"],
            estimated_assisted_minutes=entry["estimated_assisted_minutes"],
            input_schema=entry["input_schema"],
            guidance=entry["guidance"],
            current_version=max(v["version"] for v in entry["versions"]),
        )
        db.add(workflow)
        await db.flush()

        for version_entry in entry["versions"]:
            db.add(
                WorkflowVersion(
                    workflow_id=workflow.id,
                    version=version_entry["version"],
                    system_prompt=version_entry["system_prompt"],
                    prompt_template=version_entry["prompt_template"],
                    model=version_entry.get("model", MODEL_BY_WORKFLOW_DEFAULT),
                    temperature=version_entry["temperature"],
                    evaluation_rubric=version_entry["evaluation_rubric"],
                    changelog=version_entry["changelog"],
                    created_by=admin.id,
                    is_active=version_entry["is_active"],
                )
            )
        workflows[entry["slug"]] = workflow

    await db.flush()
    return workflows


async def seed_training(db: AsyncSession) -> list[TrainingModule]:
    modules = []
    for entry in load_json("training.json"):
        module = TrainingModule(
            slug=entry["slug"],
            title=entry["title"],
            summary=entry["summary"],
            body=entry["body"],
            minutes=entry["minutes"],
            order_index=entry["order_index"],
            target_roles=entry["target_roles"],
        )
        db.add(module)
        modules.append(module)
    await db.flush()
    return modules


async def seed_policies(db: AsyncSession) -> None:
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
    await db.flush()


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def dimension_scores(rng: random.Random, overall: float, rubric: dict) -> dict:
    """Spread an overall score across the dimensions the rubric actually uses."""
    weights = rubric.get("weights", {})
    scores: dict[str, float | None] = {
        "relevance": None,
        "completeness": None,
        "groundedness": None,
        "format_compliance": None,
        "clarity": None,
    }
    for dimension in scores:
        if dimension in weights or dimension in ("relevance", "completeness", "clarity"):
            scores[dimension] = round(clamp(overall + rng.gauss(0, 3.5)), 1)
    # Groundedness only exists where the workflow supplies reference material.
    if "groundedness" not in weights:
        scores["groundedness"] = None
    # Deterministic format checks are pass/fail-ish, so they cluster high.
    if scores["format_compliance"] is not None:
        scores["format_compliance"] = round(clamp(overall + rng.gauss(6, 4)), 1)
    return scores


async def seed_history(
    db: AsyncSession,
    *,
    rng: random.Random,
    users: list[User],
    departments: dict[str, Department],
    workflows: dict[str, Workflow],
) -> int:
    """Generate synthetic execution history with evaluations and feedback."""
    versions_by_workflow: dict[str, list[WorkflowVersion]] = {}
    for workflow in workflows.values():
        rows = (
            (
                await db.execute(
                    select(WorkflowVersion)
                    .where(WorkflowVersion.workflow_id == workflow.id)
                    .order_by(WorkflowVersion.version)
                )
            )
            .scalars()
            .all()
        )
        versions_by_workflow[workflow.slug] = list(rows)

    department_names = {dept.id: name for name, dept in departments.items()}

    # Decide who has adopted, per department.
    adopters: list[User] = []
    for user in users:
        department_name = department_names.get(user.department_id, "Operations")
        if rng.random() < DEPARTMENT_ADOPTION.get(department_name, 0.5):
            adopters.append(user)
    # The demo accounts always have history so a reviewer sees data on login.
    for user in users:
        if user.email.endswith("@demo.com") and user not in adopters:
            adopters.append(user)

    # Usage is long-tailed, and some people tried the platform and stopped.
    # Without that shape every adopter is a power user, "has a licence" and
    # "is actually using it" collapse into the same number, and the adoption
    # dashboard stops saying anything an enablement lead could act on.
    profiles: dict[str, dict] = {}
    for user in adopters:
        roll = rng.random()
        if roll < LAPSED_SHARE:
            profile = {"weight": rng.uniform(0.4, 1.6), "lapsed": True}
        elif roll < LAPSED_SHARE + TRIALIST_SHARE:
            profile = {"weight": rng.uniform(0.3, 1.2), "lapsed": False}
        elif roll < LAPSED_SHARE + TRIALIST_SHARE + REGULAR_SHARE:
            profile = {"weight": rng.uniform(2.0, 6.0), "lapsed": False}
        else:
            profile = {"weight": rng.uniform(7.0, 18.0), "lapsed": False}
        profiles[user.id] = profile
    for user in adopters:
        if user.email.endswith("@demo.com"):
            profiles[user.id] = {"weight": 14.0, "lapsed": False}

    adopter_weights = [profiles[user.id]["weight"] for user in adopters]

    # Which workflows a given role plausibly runs.
    role_workflows: dict[str, list[str]] = {
        "Developer": ["generate_unit_tests", "explain_code", "review_code_defects"],
        "Support": ["draft_customer_response", "categorize_support_ticket"],
        "Marketing": ["generate_campaign_variants", "analyze_customer_feedback"],
        "Finance": ["explain_variance_report", "summarize_financial_narrative"],
        "HR": ["improve_job_description", "summarize_interview_notes"],
        "Manager": ["summarize_meeting_notes", "meeting_notes_to_action_items"],
    }
    shared = ["summarize_meeting_notes", "meeting_notes_to_action_items"]

    now = datetime.now(UTC).replace(tzinfo=None)
    created = 0

    for _ in range(TARGET_EXECUTIONS):
        user = rng.choices(adopters, weights=adopter_weights, k=1)[0]
        candidates = list(role_workflows.get(user.job_role, shared))
        if user.job_role != "Manager" and rng.random() < 0.25:
            candidates += shared
        candidates = [slug for slug in candidates if slug in versions_by_workflow]
        if not candidates:
            continue

        weights = [WORKFLOW_WEIGHT.get(slug, 5) for slug in candidates]
        slug = rng.choices(candidates, weights=weights, k=1)[0]
        workflow = workflows[slug]
        versions = versions_by_workflow[slug]

        # Older executions used older prompt versions; usage migrates forward.
        if profiles[user.id]["lapsed"]:
            # Tried it early in the window, then stopped.
            age_days = rng.uniform(LAPSED_MIN_AGE_DAYS, HISTORY_DAYS)
        else:
            age_days = rng.triangular(0, HISTORY_DAYS, HISTORY_DAYS * 0.35)
        progress = 1 - (age_days / HISTORY_DAYS)  # 0 = oldest, 1 = newest
        index = min(len(versions) - 1, int(progress * len(versions)))
        if rng.random() < 0.12 and index > 0:  # a little overlap at the boundary
            index -= 1
        version = versions[index]

        created_at = now - timedelta(
            days=age_days, hours=rng.uniform(0, 23), minutes=rng.uniform(0, 59)
        )

        mean, sd = WORKFLOW_QUALITY.get(slug, (86.0, 6.0))
        penalty = VERSION_PENALTY.get(version.version, 0.0)
        # Single-version workflows have no improvement curve to model.
        if len(versions) == 1:
            penalty = 0.0
        overall = clamp(rng.gauss(mean + penalty, sd))

        # Enterprise inputs are long: a pasted policy, a diff, a transcript.
        input_tokens = rng.randint(700, 6000)
        output_tokens = rng.randint(250, 1800)

        execution = Execution(
            user_id=user.id,
            workflow_id=workflow.id,
            workflow_version_id=version.id,
            inputs={"_seeded": True},
            rendered_prompt="",
            output=SAMPLE_OUTPUT_NOTE,
            model=version.model,
            provider="openai",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=rng.randint(900, 4200),
            estimated_cost=estimate_cost(version.model, input_tokens, output_tokens),
            status=ExecutionStatus.COMPLETED,
            created_at=created_at,
        )
        db.add(execution)
        await db.flush()

        rubric = version.evaluation_rubric or {}
        scores = dimension_scores(rng, overall, rubric)
        db.add(
            EvaluationResult(
                execution_id=execution.id,
                relevance=scores["relevance"],
                completeness=scores["completeness"],
                groundedness=scores["groundedness"],
                clarity=scores["clarity"],
                format_compliance=scores["format_compliance"],
                safety_passed=rng.random() > 0.004,
                overall_score=round(overall, 1),
                deterministic_checks=[],
                evaluation_model=settings.evaluation_model,
                evaluation_reasoning="Seeded historical evaluation.",
                rubric_used=rubric,
                created_at=created_at,
            )
        )

        # Not everything gets reviewed; higher-risk workflows get reviewed more.
        review_probability = 0.9 if workflow.requires_human_review else 0.62
        if rng.random() < review_probability:
            # Approval correlates with the evaluation score but is not identical
            # to it - that gap is the point of keeping both signals.
            approval_chance = clamp((overall - 45) / 45, 0.05, 0.97)
            roll = rng.random()
            if roll < approval_chance:
                decision = FeedbackDecision.APPROVED
            elif roll < approval_chance + 0.7 * (1 - approval_chance):
                decision = FeedbackDecision.NEEDS_EDITING
            else:
                decision = FeedbackDecision.REJECTED

            db.add(
                HumanFeedback(
                    execution_id=execution.id,
                    user_id=user.id,
                    decision=decision,
                    approved=decision == FeedbackDecision.APPROVED,
                    edited=decision == FeedbackDecision.NEEDS_EDITING,
                    thumbs_up=decision != FeedbackDecision.REJECTED,
                    rating=(
                        rng.randint(4, 5)
                        if decision == FeedbackDecision.APPROVED
                        else rng.randint(1, 3)
                    ),
                    comment="",
                    created_at=created_at + timedelta(minutes=rng.randint(1, 45)),
                )
            )

        created += 1
        if created % 250 == 0:
            await db.commit()

    await db.commit()
    return created


async def seed_violations(
    db: AsyncSession, rng: random.Random, users: list[User], workflows: dict[str, Workflow]
) -> int:
    """A handful of audit records so the governance page is not empty."""
    now = datetime.now(UTC).replace(tzinfo=None)
    samples = [
        ("summarize_interview_notes", "SSN", 1, "HIGH"),
        ("draft_customer_response", "CREDIT_CARD", 1, "HIGH"),
        ("improve_job_description", "API_KEY", 1, "HIGH"),
        ("analyze_customer_feedback", "EMAIL", 12, "MEDIUM"),
        ("summarize_interview_notes", "PHONE", 2, "MEDIUM"),
        ("explain_variance_report", "SSN", 1, "HIGH"),
    ]
    count = 0
    for slug, detection_type, detections, severity in samples:
        workflow = workflows.get(slug)
        if workflow is None:
            continue
        db.add(
            PolicyViolation(
                user_id=rng.choice(users).id,
                workflow_id=workflow.id,
                policy_key="sensitive_data_detection",
                violation_type=ViolationType.SENSITIVE_DATA,
                severity=severity,
                blocked=True,
                details={
                    "detections": [{"type": detection_type, "count": detections, "field": "input"}],
                    "reason": (
                        f"{detection_type} detected; workflow is approved for "
                        f"{workflow.allowed_data_classification} data only."
                    ),
                },
                created_at=now - timedelta(days=rng.randint(1, 60), hours=rng.randint(0, 23)),
            )
        )
        count += 1

    prohibited = workflows.get("auto_reject_applicant")
    if prohibited is not None:
        db.add(
            PolicyViolation(
                user_id=rng.choice(users).id,
                workflow_id=prohibited.id,
                policy_key="prohibited_use",
                violation_type=ViolationType.PROHIBITED_USE,
                severity="PROHIBITED",
                blocked=True,
                details={
                    "detections": [],
                    "reason": "Automated adverse employment decisions are prohibited.",
                },
                created_at=now - timedelta(days=rng.randint(1, 45)),
            )
        )
        count += 1

    await db.commit()
    return count


async def seed_training_progress(
    db: AsyncSession, rng: random.Random, users: list[User], modules: list[TrainingModule]
) -> int:
    count = 0
    for user in users:
        if rng.random() > 0.55:
            continue
        completed = rng.randint(1, len(modules))
        for module in modules[:completed]:
            if module.target_roles and user.job_role not in module.target_roles:
                continue
            db.add(TrainingCompletion(user_id=user.id, module_id=module.id))
            count += 1
    await db.commit()
    return count


async def run(force: bool = False) -> None:
    rng = random.Random(RANDOM_SEED)

    async with SessionLocal() as db:
        if await already_seeded(db):
            if not force:
                print("Database already seeded. Re-run with --force to rebuild.")
                return
            print("Wiping existing demo data...")
            await wipe(db)

        print("Seeding organisation and users...")
        org_data = await seed_organisation(db, rng)
        users = org_data["users"]
        admin = next(user for user in users if user.system_role == SystemRole.ADMIN)

        print("Seeding workflow catalogue...")
        workflows = await seed_workflows(db, admin)

        print("Seeding governance policies...")
        await seed_policies(db)

        print("Seeding training modules...")
        modules = await seed_training(db)
        await db.commit()

        print(f"Generating ~{TARGET_EXECUTIONS} historical executions...")
        executions = await seed_history(
            db,
            rng=rng,
            users=users,
            departments=org_data["departments"],
            workflows=workflows,
        )

        violations = await seed_violations(db, rng, users, workflows)
        completions = await seed_training_progress(db, rng, users, modules)

        print(
            f"Done. {len(users)} users, {len(workflows)} workflows, "
            f"{executions} executions, {violations} policy violations, "
            f"{completions} training completions."
        )
        print(f"Demo logins: employee@demo.com / manager@demo.com / admin@demo.com "
              f"(password: {settings.demo_password})")

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the demo dataset.")
    parser.add_argument("--force", action="store_true", help="Wipe and rebuild demo data")
    args = parser.parse_args()
    asyncio.run(run(force=args.force))


if __name__ == "__main__":
    main()
