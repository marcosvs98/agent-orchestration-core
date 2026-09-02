from uuid import uuid4


def aggregate_cost(agent_runs: list[dict]) -> dict[str, float]:
    seen = set()
    totals: dict[str, float] = {}
    for run in agent_runs:
        run_id = run["agent_run_id"]
        if run_id in seen:
            continue
        seen.add(run_id)
        tenant = run["tenant_id"]
        totals[tenant] = totals.get(tenant, 0.0) + run.get("estimated_cost", 0.0)
    return totals


def test_replay_does_not_duplicate_cost():
    tenant = str(uuid4())
    run_id = str(uuid4())
    runs = [
        {"agent_run_id": run_id, "tenant_id": tenant, "estimated_cost": 0.5},
        {
            "agent_run_id": run_id,
            "tenant_id": tenant,
            "estimated_cost": 0.5,
        },  # replayed view of same run
        {"agent_run_id": str(uuid4()), "tenant_id": tenant, "estimated_cost": 1.0},
    ]
    totals = aggregate_cost(runs)
    assert totals[tenant] == 1.5  # dedup same run id, count distinct runs only
