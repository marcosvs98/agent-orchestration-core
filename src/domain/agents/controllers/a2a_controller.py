from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, status

from domain.agents.schemas.a2a import (
    A2AAgentCard,
    A2AErrorCode,
    A2AMessage,
    A2AMethod,
    A2ATaskState,
    JsonRpcError,
    JsonRpcRequest,
    JsonRpcResponse,
)
from domain.agents.services.a2a_translator import A2ATranslator
from domain.agents.services.agent_card_service import AgentCardService
from domain.common.schemas.error import ErrorResponse
from domain.execution.schemas.agent_run import AgentRunCreate, AgentRunDetail
from exceptions.service_exceptions import BaseServiceException
from services.execution_boundary import ExecutionBoundary
from utils.auth import AuthContext, get_auth_context


class A2AController:
    """A2A server surface: agent discovery plus the JSON-RPC task methods.

    This is the adaptation layer, not a second runtime. ``message/send`` becomes an ordinary
    agent run and the resulting run is translated back into an A2A Task, so a task submitted by
    a peer agent gets the same lifecycle, grant and transcript as one submitted over the native
    execution API.
    """

    def __init__(
        self,
        boundary: ExecutionBoundary,
        agent_card_service: AgentCardService,
        translator: A2ATranslator,
    ) -> None:
        self.boundary = boundary
        self.agent_card_service = agent_card_service
        self.translator = translator
        self.router = APIRouter(
            prefix="/core/v1/agents",
            tags=["a2a"],
            dependencies=[Depends(get_auth_context)],
        )
        self._bind_routes()

    def _bind_routes(self) -> None:
        r = self.router.add_api_route
        r(
            "/{agent_id}/agent-card",
            self.get_agent_card,
            methods=["GET"],
            response_model=A2AAgentCard,
            response_model_by_alias=True,
            responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
        )
        r(
            "/{agent_id}/a2a",
            self.handle_json_rpc,
            methods=["POST"],
            response_model=JsonRpcResponse,
        )

    async def get_agent_card(
        self, agent_id: UUID, auth: AuthContext = Depends(get_auth_context)
    ) -> A2AAgentCard:
        return await self.agent_card_service.build_agent_card(
            tenant_id=auth.tenant_id, agent_id=agent_id
        )

    async def handle_json_rpc(
        self,
        agent_id: UUID,
        rpc: JsonRpcRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> JsonRpcResponse:
        try:
            if rpc.method == A2AMethod.MESSAGE_SEND:
                result = await self._message_send(auth=auth, agent_id=agent_id, params=rpc.params)
            elif rpc.method == A2AMethod.TASKS_GET:
                result = await self._tasks_get(auth=auth, params=rpc.params)
            elif rpc.method == A2AMethod.TASKS_CANCEL:
                result = await self._tasks_cancel(auth=auth, params=rpc.params)
            else:
                return self._error(
                    rpc.id,
                    A2AErrorCode.METHOD_NOT_FOUND,
                    "method_not_found",
                    {"method": rpc.method},
                )
        except ValueError as exc:
            return self._error(
                rpc.id, A2AErrorCode.INVALID_PARAMS, "invalid_params", {"detail": str(exc)}
            )
        except BaseServiceException as exc:
            code = (
                A2AErrorCode.TASK_NOT_FOUND
                if exc.status_code == status.HTTP_404_NOT_FOUND
                else A2AErrorCode.INTERNAL_ERROR
            )
            return self._error(rpc.id, code, exc.message, {"name": exc.name})
        return JsonRpcResponse(id=rpc.id, result=result)

    async def _message_send(
        self, *, auth: AuthContext, agent_id: UUID, params: dict
    ) -> dict[str, object]:
        raw_message = params.get("message")
        if not isinstance(raw_message, dict):
            raise ValueError("message_required")
        message = A2AMessage.model_validate(raw_message)
        instruction = message.text().strip()
        if not instruction:
            raise ValueError("message_text_part_required")

        summary = await self.boundary.create_agent_run(
            auth=auth,
            endpoint="/core/v1/agents/a2a",
            idempotency_key=message.message_id or uuid4().hex,
            agent_run=AgentRunCreate(
                agent_id=agent_id,
                instruction=instruction,
                payload=message.data(),
                metadata={"a2a_context_id": message.context_id or ""},
            ),
            wait=True,
        )
        detail = await self.boundary.get_agent_run(auth=auth, agent_run_id=summary.id)
        return self._task_from_run(detail).model_dump(mode="json")

    async def _tasks_get(self, *, auth: AuthContext, params: dict) -> dict[str, object]:
        detail = await self.boundary.get_agent_run(
            auth=auth, agent_run_id=self._task_id_to_run_id(params)
        )
        return self._task_from_run(detail).model_dump(mode="json")

    async def _tasks_cancel(self, *, auth: AuthContext, params: dict) -> dict[str, object]:
        summary = await self.boundary.cancel_agent_run(
            auth=auth, agent_run_id=self._task_id_to_run_id(params)
        )
        detail = await self.boundary.get_agent_run(auth=auth, agent_run_id=summary.id)
        return self._task_from_run(detail).model_dump(mode="json")

    @staticmethod
    def _task_id_to_run_id(params: dict) -> UUID:
        raw_id = params.get("id")
        if not isinstance(raw_id, str) or not raw_id.strip():
            raise ValueError("id_required")
        try:
            return UUID(raw_id)
        except ValueError as exc:
            raise ValueError("invalid_task_id") from exc

    def _task_from_run(self, detail: AgentRunDetail):
        task_id = str(detail.id)
        context_id = str(detail.root_agent_run_id or detail.id)
        state = self.translator.task_state_for_run_status(detail.canonical_status)
        output_text = str((detail.output or {}).get("text") or "")
        status_message = (
            self.translator.build_agent_message(
                task_id=task_id, context_id=context_id, text=output_text
            )
            if output_text
            else None
        )
        history = [status_message] if status_message is not None else []
        artifacts = [
            self.translator.build_output_artifact(
                index=artifact.index,
                name=str(artifact.name or "artifact"),
                description=artifact.description,
                text="\n".join(
                    str(part.get("text", ""))
                    for part in artifact.parts
                    if part.get("kind") == "text"
                ),
            )
            for artifact in detail.artifacts
        ]
        return self.translator.build_task(
            task_id=task_id,
            context_id=context_id,
            state=state if state != A2ATaskState.UNKNOWN else A2ATaskState.UNKNOWN,
            history=history,
            artifacts=artifacts,
            status_message=status_message,
            metadata={
                "agent_id": str(detail.agent_id),
                "agent_version_id": str(detail.agent_version_id),
                "finish_reason": detail.finish_reason.value if detail.finish_reason else None,
            },
        )

    @staticmethod
    def _error(
        rpc_id: str | int | None,
        code: A2AErrorCode,
        message: str,
        data: dict[str, object],
    ) -> JsonRpcResponse:
        return JsonRpcResponse(
            id=rpc_id, error=JsonRpcError(code=int(code), message=message, data=data)
        )
