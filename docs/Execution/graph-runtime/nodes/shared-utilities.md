# Shared node utilities

`_common.py` (`src/domain/execution/services/graph_runtime/nodes/_common.py`) provides small helpers reused by multiple nodes.

## `read_user_input(context)`

Returns the string in `context.input_payload["user_input"]` when `input_payload` is a dict; otherwise `""`. Used by **`ContentModeration`**, **`LLMNodeExecutor`** (via input flow), and others.

## `conversation_key_and_stateless(task_type, llm_policy, tenant_id, session_id, use_history_override)`

Computes **`conversation_key`** (`"{tenant_id}:{session_id}"` or `None`) and **`stateless`** flag for LLM history behaviour from `llm_policy["history_enabled_tasks"]` and optional override — see call sites in `_llm_base.py`.

## Related

- [LLM node base](llm-node-base.md)
