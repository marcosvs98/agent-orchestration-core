# Tool config

## Definition

**Tool config** holds **versioned** OpenAPI (or equivalent) definitions and metadata so the platform can **validate**, **resolve**, and **execute** HTTP or MCP-backed tools in a governed way.

## What it is not

- Not a single HTTP call: execution produces a [Flow run](flow-run.md) scoped **tool run** with events.
- Not unversioned: changes should flow through authoring/version records.

## Code

- `src/domain/tools/`
- Execution: `src/infra/http_tool_executor.py` and tool orchestration services.

## Persistence

- `tool`, `tool_config`, `tool_run`; MCP linkage via `mcp_server*`. See [persistence tables](../persistence-tables.md) and [MCP](../persistence-tables.md).

## Related

- [Agent version](agent-version.md)
- [Execution event](execution-event.md)
