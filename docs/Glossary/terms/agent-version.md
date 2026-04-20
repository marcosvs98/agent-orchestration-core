# Agent version

## Definition

An **agent version** is a **versioned agent definition** bound to tools and policies for execution. Bindings (e.g. agent–tool links) are recorded so runtime can resolve which tools an agent may invoke in a given flow context.

## What it is not

- Not the same as [Flow run](flow-run.md) or `agent_run` (runtime invocation record).

## Code

- `src/domain/agents/`

## Persistence

- `agent`, `agent_version`, `agent_version_tool_binding`, `node_agent_binding`. See [persistence tables](../persistence-tables.md).

## Related

- [Tool config](tool-config.md)
- [Flow run](flow-run.md)
