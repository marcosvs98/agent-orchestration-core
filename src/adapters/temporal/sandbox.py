from __future__ import annotations

from temporalio.worker.workflow_sandbox import SandboxedWorkflowRunner, SandboxRestrictions

PASSTHROUGH_MODULES = (
    "beartype",
    "adapters",
    "domain",
    "infra",
    "services",
    "exceptions",
    "utils",
    "application",
    "settings",
)


def build_workflow_runner() -> SandboxedWorkflowRunner:
    """Sandbox runner for FlowRunWorkflow.

    fastmcp installs a beartype import hook at import time, and the worker
    process imports it transitively through ApplicationContainer. Re-importing
    modules inside the sandbox then trips a circular import in beartype.claw.
    Application packages are passed through as well: the workflow only ever
    touches the pure DTO module, so reloading them buys no determinism and
    costs worker startup time.
    """
    return SandboxedWorkflowRunner(
        restrictions=SandboxRestrictions.default.with_passthrough_modules(*PASSTHROUGH_MODULES)
    )
