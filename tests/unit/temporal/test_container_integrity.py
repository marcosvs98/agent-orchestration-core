"""Guards that the Temporal worker can build its dependencies from ApplicationContainer.

The arq embedding worker drifted into an unstartable state because it hand-built
its own DI graph. The Temporal worker reuses ApplicationContainer instead; this
test fails the moment that graph stops constructing.
"""

from containers import ApplicationContainer


def test_execution_service_resolves_with_full_node_graph() -> None:
    container = ApplicationContainer()
    container.config.from_dict({"application_name": "test"})

    execution_service = container.execution.execution_service()

    assert execution_service.repository is not None
    assert execution_service.runtime is not None
    assert execution_service.runtime.registry is not None
    assert execution_service.runtime.step_runner is not None
    assert execution_service.hook is not None
    assert execution_service.plan_compiler is not None
    assert execution_service.policy_resolver is not None
    assert execution_service.workflow_engine is not None


def test_flow_run_activities_construct_from_container() -> None:
    from adapters.temporal.activities import FlowRunActivities

    container = ApplicationContainer()
    container.config.from_dict({"application_name": "test"})

    activities = FlowRunActivities(
        execution_service=container.execution.execution_service(),
        tracer=container.adapters.tracer(),
    )

    assert activities.step_runner is not None
    assert activities.plan_compiler is not None
    assert activities.policy_resolver is not None
    assert activities.idempotency is not None
