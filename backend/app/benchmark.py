"""Command-line benchmark runner.

    python -m app.benchmark --workflow generate_unit_tests
    python -m app.benchmark --workflow explain_variance_report --versions 1 2

Runs the seeded evaluation cases for a workflow against one or more prompt
versions and prints the comparison. With AI_PROVIDER=stub this costs nothing
and is deterministic; with AI_PROVIDER=openai it makes real calls.
"""

import argparse
import asyncio

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.enums import SystemRole
from app.models.user import User
from app.models.workflow import WorkflowVersion
from app.repositories import workflow_repo
from app.services.benchmark_service import benchmark_version, compare, load_cases


def _print_table(summaries: list[dict]) -> None:
    columns = [
        ("version", "Version", 8),
        ("average_quality", "Quality", 9),
        ("relevance", "Relev.", 8),
        ("completeness", "Compl.", 8),
        ("groundedness", "Ground.", 9),
        ("format_compliance", "Format", 8),
        ("average_cost", "Cost", 10),
        ("average_latency_ms", "Latency", 9),
    ]
    header = "".join(label.ljust(width) for _, label, width in columns)
    print(header)
    print("-" * len(header))
    for summary in summaries:
        row = ""
        for key, _, width in columns:
            value = summary.get(key)
            if key == "version":
                text = f"v{value}"
            elif key == "average_cost":
                text = f"${value:.5f}"
            elif key == "average_latency_ms":
                text = f"{value}ms"
            else:
                text = "n/a" if value is None else str(value)
            row += text.ljust(width)
        print(row)


async def run(workflow_slug: str, version_numbers: list[int] | None) -> None:
    cases = load_cases(workflow_slug)
    if not cases:
        print(f"No benchmark cases defined for '{workflow_slug}'.")
        return

    async with SessionLocal() as db:
        workflow = await workflow_repo.get_workflow_by_slug(db, workflow_slug)
        if workflow is None:
            print(f"Workflow '{workflow_slug}' not found. Has the database been seeded?")
            return

        user = (
            await db.execute(
                select(User).where(User.system_role == SystemRole.ADMIN).limit(1)
            )
        ).scalars().first()
        if user is None:
            print("No admin user found. Run `python -m app.seed` first.")
            return

        versions = (
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
        if version_numbers:
            versions = [v for v in versions if v.version in version_numbers]
        if not versions:
            print("No matching versions.")
            return

        print(
            f"\n{workflow.name}  -  {len(cases)} benchmark cases  -  "
            f"provider={settings.ai_provider}\n"
        )
        if settings.ai_provider == "stub":
            print(
                "NOTE: the stub provider returns fixtures derived from the input and\n"
                "      ignores the system prompt, so version-to-version differences\n"
                "      below are not meaningful. Set AI_PROVIDER=openai to compare\n"
                "      prompts for real.\n"
            )

        benchmarks = []
        for version in versions:
            print(f"Running v{version.version} ({version.model})...")
            benchmarks.append(
                await benchmark_version(
                    db, user=user, workflow=workflow, version=version, cases=cases
                )
            )

        print()
        _print_table([benchmark.summary() for benchmark in benchmarks])

        governance = benchmarks[-1].summary()
        if governance["governance_cases"]:
            print(
                f"\nGovernance: {governance['governance_blocked']}/"
                f"{governance['governance_cases']} cases expected to be blocked were blocked."
            )

        failures = [
            case
            for case in benchmarks[-1].cases
            if not case.passed_expectation
        ]
        if failures:
            print("\nCases that did not meet their expected behaviour:")
            for case in failures:
                print(f"  - {case.case_id} ({case.case_type}): expected {case.expected_behaviour}")

        if len(benchmarks) >= 2:
            print("\n" + compare(benchmarks[-2], benchmarks[-1]))
        print()

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run benchmark cases for a workflow.")
    parser.add_argument("--workflow", required=True, help="Workflow slug")
    parser.add_argument(
        "--versions", nargs="*", type=int, default=None, help="Version numbers to run"
    )
    args = parser.parse_args()
    asyncio.run(run(args.workflow, args.versions))


if __name__ == "__main__":
    main()
