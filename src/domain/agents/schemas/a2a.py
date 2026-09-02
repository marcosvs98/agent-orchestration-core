from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

A2A_PROTOCOL_VERSION = "0.3.0"


class A2AModel(BaseModel):
    """Wire shape of the Agent2Agent protocol.

    The protocol is camelCase; the rest of this codebase is snake_case. Aliases keep both true
    at once so no translation code has to hand-copy field names.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
    )


class A2ATaskState(StrEnum):
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    CANCELED = "canceled"
    FAILED = "failed"
    REJECTED = "rejected"
    AUTH_REQUIRED = "auth-required"
    UNKNOWN = "unknown"


TERMINAL_TASK_STATES = frozenset(
    {
        A2ATaskState.COMPLETED,
        A2ATaskState.CANCELED,
        A2ATaskState.FAILED,
        A2ATaskState.REJECTED,
    }
)


class A2ARole(StrEnum):
    USER = "user"
    AGENT = "agent"


class A2ATextPart(A2AModel):
    kind: Literal["text"] = "text"
    text: str
    metadata: dict[str, Any] | None = None


class A2AFileWithUri(A2AModel):
    name: str | None = None
    mime_type: str | None = None
    uri: str


class A2AFileWithBytes(A2AModel):
    name: str | None = None
    mime_type: str | None = None
    bytes: str


class A2AFilePart(A2AModel):
    kind: Literal["file"] = "file"
    file: A2AFileWithUri | A2AFileWithBytes
    metadata: dict[str, Any] | None = None


class A2ADataPart(A2AModel):
    kind: Literal["data"] = "data"
    data: dict[str, Any]
    metadata: dict[str, Any] | None = None


A2APart = Annotated[
    A2ATextPart | A2AFilePart | A2ADataPart,
    Field(discriminator="kind"),
]


class A2AMessage(A2AModel):
    kind: Literal["message"] = "message"
    message_id: str
    role: A2ARole
    parts: list[A2APart] = Field(default_factory=list)
    task_id: str | None = None
    context_id: str | None = None
    reference_task_ids: list[str] | None = None
    metadata: dict[str, Any] | None = None

    def text(self) -> str:
        return "\n".join(part.text for part in self.parts if isinstance(part, A2ATextPart))

    def data(self) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for part in self.parts:
            if isinstance(part, A2ADataPart):
                merged.update(part.data)
        return merged


class A2AArtifact(A2AModel):
    artifact_id: str
    name: str | None = None
    description: str | None = None
    parts: list[A2APart] = Field(default_factory=list)
    metadata: dict[str, Any] | None = None


class A2ATaskStatus(A2AModel):
    state: A2ATaskState
    message: A2AMessage | None = None
    timestamp: str | None = None


class A2ATask(A2AModel):
    kind: Literal["task"] = "task"
    id: str
    context_id: str
    status: A2ATaskStatus
    history: list[A2AMessage] = Field(default_factory=list)
    artifacts: list[A2AArtifact] = Field(default_factory=list)
    metadata: dict[str, Any] | None = None


class A2AAgentCapabilities(A2AModel):
    streaming: bool = False
    push_notifications: bool = False
    state_transition_history: bool = True


class A2AAgentProvider(A2AModel):
    organization: str
    url: str


class A2AAgentSkill(A2AModel):
    id: str
    name: str
    description: str
    tags: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    input_modes: list[str] | None = None
    output_modes: list[str] | None = None


class A2AAgentCard(A2AModel):
    protocol_version: str = A2A_PROTOCOL_VERSION
    name: str
    description: str
    url: str
    preferred_transport: str = "JSONRPC"
    version: str
    provider: A2AAgentProvider | None = None
    documentation_url: str | None = None
    capabilities: A2AAgentCapabilities = Field(default_factory=A2AAgentCapabilities)
    security_schemes: dict[str, Any] | None = None
    security: list[dict[str, list[str]]] | None = None
    default_input_modes: list[str] = Field(default_factory=lambda: ["text/plain"])
    default_output_modes: list[str] = Field(default_factory=lambda: ["text/plain"])
    skills: list[A2AAgentSkill] = Field(default_factory=list)
    supports_authenticated_extended_card: bool = False


class A2AMethod(StrEnum):
    MESSAGE_SEND = "message/send"
    TASKS_GET = "tasks/get"
    TASKS_CANCEL = "tasks/cancel"


class A2AErrorCode(IntEnum):
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    TASK_NOT_FOUND = -32001
    TASK_NOT_CANCELABLE = -32002
    PUSH_NOTIFICATION_NOT_SUPPORTED = -32003
    UNSUPPORTED_OPERATION = -32004
    CONTENT_TYPE_NOT_SUPPORTED = -32005
    INVALID_AGENT_RESPONSE = -32006


class JsonRpcError(BaseModel):
    code: int
    message: str
    data: dict[str, Any] | None = None


class JsonRpcRequest(BaseModel):
    jsonrpc: Literal["2.0"]
    method: str
    id: str | int | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class JsonRpcResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int | None = None
    result: dict[str, Any] | None = None
    error: JsonRpcError | None = None


class A2ADelegationRequest(BaseModel):
    """What a running agent asks for when it needs another agent's capability."""

    tenant_id: UUID
    principal_id: str
    parent_agent_run_id: UUID
    root_agent_run_id: UUID
    delegation_depth: int
    correlation_id: UUID
    target_agent_id: UUID
    instruction: str
    payload: dict[str, Any] = Field(default_factory=dict)
    allowed_tool_names: list[str] | None = None
    max_iterations: int | None = None

    model_config = ConfigDict(frozen=True)


class A2ATaskExecution(BaseModel):
    """One A2A task handed to a transport for execution.

    The in-process transport turns it into a child agent run; a remote transport would put the
    same fields on the wire as ``message/send``. Both keep ``task_id``/``context_id`` stable so
    the parent run and the delegated run stay correlated either way.
    """

    tenant_id: UUID
    principal_id: str
    target_agent_id: UUID
    task_id: str
    context_id: str
    message: A2AMessage
    parent_agent_run_id: UUID | None = None
    root_agent_run_id: UUID | None = None
    delegation_depth: int = 0
    correlation_id: UUID
    allowed_tool_names: list[str] | None = None
    max_iterations: int | None = None

    model_config = ConfigDict(frozen=True)


class A2ATaskExecutionResult(BaseModel):
    state: A2ATaskState
    child_agent_run_id: UUID | None = None
    output_text: str = ""
    artifacts: list[A2AArtifact] = Field(default_factory=list)
    error: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class A2ADelegationOutcome(BaseModel):
    agent_delegation_id: UUID
    task: A2ATask
    child_agent_run_id: UUID | None = None
    output_text: str = ""

    model_config = ConfigDict(frozen=True)
