from enum import StrEnum


class Scope(StrEnum):
    ExecutionFlowRunCreate = "execution:flow_run:create"
    ExecutionToolRunCreate = "execution:tool_run:create"
    ExecutionToolRunExecute = "execution:tool_run:execute"
    ExecutionEventsList = "execution:events:list"
