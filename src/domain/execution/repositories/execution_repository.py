import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import aliased

from domain.execution.schemas.execution import (
    FlowRunInput,
    UserPreferenceUpsertResult,
)
from adapters.cache.redis_adapter import RedisAdapter
from infra.database.models.conversation.session import Session as SessionModel
from infra.database.models.conversation.user import User as UserModel
from infra.database.models.conversation.user_memory_profile import (
    UserMemoryProfile as UserMemoryProfileModel,
)
from exceptions.service_exceptions import (
    DomainConflictException,
    DomainValidationException,
    NotFoundServiceException,
)
from infra.database import DatabaseConnection
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.services.state_machine import (
    FlowRunStatus,
    RunStatus,
    ToolRunStatus,
)
from utils.query_compiler import compile_query
from infra.database.models.execution.flow_run import FlowRun as FlowRunModel
from infra.database.models.execution.tool_run import ToolRun as ToolRunModel
from infra.database.models.execution.agent_run import AgentRun as AgentRunModel
from infra.database.models.execution.flow_run_lock import (
    FlowRunLock as FlowRunLockModel,
)
from infra.database.models.execution.execution_event import (
    ExecutionEvent as ExecutionEventModel,
)
from infra.database.models.execution.node_run import NodeRun as NodeRunModel
from infra.database.models.execution.run_failure import RunFailure as RunFailureModel
from infra.database.models.flow.node import Node as NodeModel
from infra.database.models.ai_policy.execution_policy_version import (
    AIExecutionPolicyVersion as AIExecutionPolicyVersionModel,
)
from infra.database.models.ai_policy.model import Model as ModelModel
from infra.database.models.agent.agent_version import AgentVersion as AgentVersionModel
from infra.database.models.flow.flow import Flow as FlowModel
from infra.database.models.flow.flow_version import FlowVersion as FlowVersionModel
from infra.database.models.flow.flow_graph import FlowGraph as FlowGraphModel
from infra.database.models.flow.flow_graph_snapshot import (
    FlowGraphSnapshot as FlowGraphSnapshotModel,
)
from infra.database.models.flow.flow_snapshot import FlowSnapshot as FlowSnapshotModel
from infra.database.models.flow.flow_deployment import (
    FlowDeployment as FlowDeploymentModel,
)
from infra.database.models.tool.tool_config import ToolConfig as ToolConfigModel
from infra.database.models.conversation.interaction import (
    Interaction as InteractionModel,
)
from infra.database.models.conversation.response_artifact import (
    ResponseArtifact as ResponseArtifactModel,
)
from infra.database.models.governance.billing_policy_version import (
    BillingPolicyVersion as BillingPolicyVersionModel,
)
from infra.database.models.governance.memory_policy_version import (
    MemoryPolicyVersion as MemoryPolicyVersionModel,
)
from infra.database.models.governance.rag_policy_version import (
    RagPolicyVersion as RagPolicyVersionModel,
)
from infra.database.models.execution.graph_state import GraphState as GraphStateModel

DEFAULT_EVENT_BATCH_SIZE = 20

_PROFILE_SCHEMA_MIN = 1
_PROFILE_SCHEMA_MAX = 1
_MEMORY_PREFS_KEY = "memory_preferences"


def _preferences_dict_from_profile(profile: dict[str, object]) -> dict[str, object]:
    raw = profile.get(_MEMORY_PREFS_KEY)
    if type(raw) != dict:
        return {}
    out: dict[str, object] = {}
    for key, entry in raw.items():
        key_str = str(key)
        if type(entry) is dict and "value" in entry:
            out[key_str] = entry["value"]
        else:
            out[key_str] = entry
    return out


def _validate_profile_schema_version(profile: dict[str, object]) -> None:
    raw = profile.get("profile_schema_version")
    if raw is None:
        return
    try:
        sv = int(raw)
    except (TypeError, ValueError) as exc:
        raise DomainValidationException(
            message="user_memory_profile_schema_invalid"
        ) from exc
    if sv < _PROFILE_SCHEMA_MIN or sv > _PROFILE_SCHEMA_MAX:
        raise DomainValidationException(
            message="user_memory_profile_schema_unsupported"
        )


class ExecutionRepository:
    def __init__(
        self,
        database_connection: DatabaseConnection,
        tracer: RuntimeTracerPort,
        cache_adapter: RedisAdapter,
        event_batch_size: int = DEFAULT_EVENT_BATCH_SIZE,
    ) -> None:
        self.db = database_connection
        self.tracer = tracer
        self.cache_adapter = cache_adapter
        self._event_batch_size = event_batch_size
        self._event_batch_buffer: dict[UUID, list[dict]] = {}
        self._batching_flow_runs: set[UUID] = set()
        self._event_batch_lock = asyncio.Lock()

    def start_event_batching(self, flow_run_id: UUID) -> None:
        """Enable batching for execution events for the given flow run."""
        self._batching_flow_runs.add(flow_run_id)
        if flow_run_id not in self._event_batch_buffer:
            self._event_batch_buffer[flow_run_id] = []

    async def _persist_execution_events_batch(
        self, flow_run_id: UUID, events: list[dict]
    ) -> None:
        if not events:
            return
        with self.tracer.observe(
            as_type="tool",
            name="domain.execution.repository.flush_execution_events",
            input={"flow_run_id": str(flow_run_id), "event_count": len(events)},
        ) as tool_handle:
            async with self.db.get_session() as session:
                first = events[0]
                user_id = first.get("user_id")
                if user_id is None:
                    flow_run_result = await session.execute(
                        select(FlowRunModel.user_id).where(
                            FlowRunModel.flow_run_id == flow_run_id
                        )
                    )
                    user_id = flow_run_result.scalar_one_or_none()
                if user_id is None:
                    raise NotFoundServiceException(message="flow_run_user_not_found")
                await session.execute(
                    select(FlowRunLockModel)
                    .where(FlowRunLockModel.flow_run_id == flow_run_id)
                    .with_for_update()
                )
                result = await session.execute(
                    select(
                        sa.func.coalesce(
                            sa.func.max(ExecutionEventModel.event_sequence), 0
                        )
                    ).where(ExecutionEventModel.flow_run_id == flow_run_id)
                )
                next_seq = int(result.scalar_one()) + 1
                for ev in events:
                    session.add(
                        ExecutionEventModel(
                            execution_event_id=ev["event_id"],
                            tenant_id=ev["tenant_id"],
                            user_id=user_id,
                            session_id=ev["session_id"],
                            flow_run_id=flow_run_id,
                            correlation_id=ev["correlation_id"],
                            causation_id=ev.get("causation_id"),
                            event_sequence=next_seq,
                            schema_version=ev.get("schema_version", 1),
                            type=ev["event_type"],
                            payload=ev["payload"],
                            node_id=ev.get("node_id"),
                            edge_id=ev.get("edge_id"),
                        )
                    )
                    next_seq += 1
                await session.commit()
                if tool_handle:
                    tool_handle.success(output={"flushed": len(events)})

    async def flush_execution_events(self, flow_run_id: UUID) -> None:
        """Persist all buffered events for the flow run in a single transaction."""
        async with self._event_batch_lock:
            self._batching_flow_runs.discard(flow_run_id)
            events = self._event_batch_buffer.pop(flow_run_id, [])
        await self._persist_execution_events_batch(flow_run_id, events)

    async def end_event_batching(self, flow_run_id: UUID) -> None:
        """Flush remaining events and disable batching for the flow run."""
        await self.flush_execution_events(flow_run_id)

    async def create_flow_run(
        self,
        *,
        session_id: UUID,
        flow_version_id: UUID,
        correlation_id: UUID,
        origin_flow_run_id: UUID | None,
        user_id: str,
        input_payload: FlowRunInput,
        interaction_id: UUID | None = None,
        flow_graph_snapshot_id: UUID | None = None,
        flow_snapshot_id: UUID | None = None,
        flow_deployment_id: UUID | None = None,
        runtime_contract: dict[str, object] | None = None,
        execution_plan_hash: str | None = None,
        runtime_policy_hash: str | None = None,
        tool_catalog_hash: str | None = None,
        llm_provider_config_hash: str | None = None,
        trace_id: UUID | None = None,
        root_observation_id: str | None = None,
    ) -> UUID:
        flow_run_id = uuid4()
        with self.tracer.observe(
            as_type="tool",
            name="domain.execution.repository.create_flow_run",
            input={
                "flow_run_id": str(flow_run_id),
                "flow_version_id": str(flow_version_id),
                "session_id": str(session_id),
                "interaction_id": str(interaction_id),
                "flow_graph_snapshot_id": str(flow_graph_snapshot_id),
                "flow_snapshot_id": str(flow_snapshot_id) if flow_snapshot_id else None,
                "flow_deployment_id": str(flow_deployment_id)
                if flow_deployment_id
                else None,
                "execution_plan_hash": execution_plan_hash,
                "runtime_policy_hash": runtime_policy_hash,
                "tool_catalog_hash": tool_catalog_hash,
                "llm_provider_config_hash": llm_provider_config_hash,
            },
        ) as tool_handle:
            async with self.db.get_session() as session:
                session.add(
                    FlowRunModel(
                        flow_run_id=flow_run_id,
                        session_id=session_id,
                        flow_version_id=flow_version_id,
                        correlation_id=correlation_id,
                        origin_flow_run_id=origin_flow_run_id,
                        user_id=user_id,
                        input=input_payload.model_dump(mode="json"),
                        interaction_id=interaction_id,
                        flow_graph_snapshot_id=flow_graph_snapshot_id,
                        flow_snapshot_id=flow_snapshot_id,
                        flow_deployment_id=flow_deployment_id,
                        runtime_contract=runtime_contract or {},
                        execution_plan_hash=execution_plan_hash,
                        runtime_policy_hash=runtime_policy_hash,
                        tool_catalog_hash=tool_catalog_hash,
                        llm_provider_config_hash=llm_provider_config_hash,
                        trace_id=trace_id,
                        root_observation_id=root_observation_id,
                    )
                )
                session.add(
                    FlowRunLockModel(
                        flow_run_id=flow_run_id,
                        locked_at=sa.func.now(),
                        owner=None,
                        correlation_id=correlation_id,
                    )
                )
                await session.commit()
                if tool_handle:
                    tool_handle.success(output={"flow_run_id": str(flow_run_id)})
        return flow_run_id

    async def merge_flow_run_runtime_contract(
        self, *, flow_run_id: UUID, patch: dict[str, object]
    ) -> None:
        async with self.db.get_session() as session:
            row = await session.get(FlowRunModel, flow_run_id)
            if row is None:
                return
            current = dict(row.runtime_contract or {})
            current.update(patch)
            row.runtime_contract = current
            await session.commit()

    async def get_active_flow_deployment(
        self, *, flow_id: UUID, environment: str = "default"
    ) -> FlowDeploymentModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(FlowDeploymentModel).where(
                    FlowDeploymentModel.flow_id == flow_id,
                    FlowDeploymentModel.environment == environment,
                    FlowDeploymentModel.status == "ACTIVE",
                )
            )
            return result.scalar_one_or_none()

    async def get_flow_snapshot_by_id(
        self, flow_snapshot_id: UUID
    ) -> FlowSnapshotModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(FlowSnapshotModel).where(
                    FlowSnapshotModel.flow_snapshot_id == flow_snapshot_id
                )
            )
            return result.scalar_one_or_none()

    async def get_flow_snapshot_by_flow_version(
        self, flow_version_id: UUID
    ) -> FlowSnapshotModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(FlowSnapshotModel).where(
                    FlowSnapshotModel.flow_version_id == flow_version_id
                )
            )
            return result.scalar_one_or_none()

    async def set_root_observation_id(
        self, *, flow_run_id: UUID, root_observation_id: str
    ) -> None:
        with self.tracer.observe(
            as_type="tool",
            name="domain.execution.repository.set_root_observation_id",
            input={"flow_run_id": str(flow_run_id)},
        ) as tool_handle:
            async with self.db.get_session() as session:
                await session.execute(
                    sa.update(FlowRunModel)
                    .where(FlowRunModel.flow_run_id == flow_run_id)
                    .values(root_observation_id=root_observation_id)
                )
                await session.commit()
                if tool_handle:
                    tool_handle.success(
                        output={
                            "flow_run_id": str(flow_run_id),
                            "root_observation_id": root_observation_id,
                        }
                    )

    async def complete_flow_run(
        self,
        *,
        flow_run_id: UUID,
        status: str,
        output: dict,
    ) -> None:
        with self.tracer.observe(
            as_type="tool",
            name="domain.execution.repository.complete_flow_run",
            input={"flow_run_id": str(flow_run_id), "status": status},
        ):
            async with self.db.get_session() as session:
                await session.execute(
                    sa.update(FlowRunModel)
                    .where(FlowRunModel.flow_run_id == flow_run_id)
                    .values(
                        status=status,
                        canonical_status=status,
                        output=output,
                        finished_at=datetime.now(timezone.utc),
                    )
                )
                await session.commit()

    async def fail_flow_run(
        self,
        *,
        flow_run_id: UUID,
        failure_reason: str,
        error: dict | None = None,
    ) -> None:
        with self.tracer.observe(
            as_type="tool",
            name="domain.execution.repository.fail_flow_run",
            input={"flow_run_id": str(flow_run_id), "reason": failure_reason},
        ):
            async with self.db.get_session() as session:
                await session.execute(
                    sa.update(FlowRunModel)
                    .where(FlowRunModel.flow_run_id == flow_run_id)
                    .values(
                        status="FAILED",
                        canonical_status="FAILED",
                        error=error or {"reason": failure_reason},
                        finished_at=datetime.now(timezone.utc),
                    )
                )
                await session.commit()

    async def set_flow_run_status(
        self,
        *,
        flow_run_id: UUID,
        status: str,
        canonical_status: str,
    ) -> None:
        with self.tracer.observe(
            as_type="tool",
            name="domain.execution.repository.set_flow_run_status",
            input={"flow_run_id": str(flow_run_id), "status": status},
        ):
            async with self.db.get_session() as session:
                await session.execute(
                    sa.update(FlowRunModel)
                    .where(FlowRunModel.flow_run_id == flow_run_id)
                    .values(
                        status=status,
                        canonical_status=canonical_status,
                    )
                )
                await session.commit()

    async def set_flow_run_output(
        self,
        *,
        flow_run_id: UUID,
        output: dict,
    ) -> None:
        with self.tracer.observe(
            as_type="tool",
            name="domain.execution.repository.set_flow_run_output",
            input={"flow_run_id": str(flow_run_id)},
        ):
            async with self.db.get_session() as session:
                await session.execute(
                    sa.update(FlowRunModel)
                    .where(FlowRunModel.flow_run_id == flow_run_id)
                    .values(output=output or {})
                )
                await session.commit()

    async def get_session(self, session_id: UUID) -> SessionModel | None:
        async with self.db.get_session() as session:
            stmt = select(SessionModel).where(SessionModel.session_id == session_id)
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_session",
                input={
                    "query": query_sql,
                    "params": {"session_id": str(session_id)},
                },
                metadata={"retriever_name": "get_session"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                session_record = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if session_record else 0,
                            "found": session_record is not None,
                        }
                    )

                return session_record

    async def create_session(
        self, *, session_id: UUID, tenant_id: UUID, user_id: str
    ) -> None:
        async with self.db.get_session() as session:
            user_result = await session.execute(
                select(UserModel).where(
                    UserModel.tenant_id == tenant_id,
                    UserModel.user_id == user_id,
                )
            )
            user_record = user_result.scalar_one_or_none()
            if user_record is None:
                session.add(UserModel(tenant_id=tenant_id, user_id=user_id))
            stmt_session = select(SessionModel).where(
                SessionModel.session_id == session_id
            )
            query_sql_session = compile_query(stmt_session)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_session_for_create",
                input={
                    "query": query_sql_session,
                    "params": {"session_id": str(session_id)},
                },
                metadata={"retriever_name": "get_session_for_create"},
            ) as retriever_handle:
                existing = await session.execute(stmt_session)
                existing_record = existing.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if existing_record else 0,
                            "found": existing_record is not None,
                        }
                    )

            if existing_record is None:
                with self.tracer.observe(
                    as_type="tool",
                    name="domain.execution.repository.create_session",
                    input={
                        "session_id": str(session_id),
                        "tenant_id": str(tenant_id),
                        "user_id": user_id,
                    },
                ) as tool_handle:
                    session.add(
                        SessionModel(
                            session_id=session_id, tenant_id=tenant_id, user_id=user_id
                        )
                    )
                    await session.commit()
                    if tool_handle:
                        tool_handle.success(output={"session_id": str(session_id)})
            else:
                if (
                    existing_record.tenant_id != tenant_id
                    or existing_record.user_id != user_id
                ):
                    raise DomainConflictException(message="session_user_mismatch")
                await session.commit()

    async def get_flow_context(self, flow_run_id: UUID) -> tuple[UUID, UUID]:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.repository.get_flow_context",
            input={"flow_run_id": str(flow_run_id)},
        ) as handle:
            flow_run = await self.get_flow_run(flow_run_id)
            if flow_run is None:
                raise NotFoundServiceException(message="flow_run_not_found")
            session_record = await self.get_session(flow_run.session_id)
            if session_record is None:
                raise NotFoundServiceException(message="session_not_found")
            if handle:
                handle.success(
                    output={
                        "result_count": 1,
                        "found": True,
                        "session_id": str(flow_run.session_id),
                        "tenant_id": str(session_record.tenant_id),
                    }
                )
            return flow_run.session_id, session_record.tenant_id

    async def get_user_preferences(self, *, tenant_id: UUID, user_id: str) -> dict:
        profile = await self.get_user_memory_profile(
            tenant_id=tenant_id, user_id=user_id
        )
        _validate_profile_schema_version(profile)
        return _preferences_dict_from_profile(profile)

    async def get_user_memory_preferences_and_profile(
        self, *, tenant_id: UUID, user_id: str
    ) -> tuple[dict[str, object], dict[str, object]]:
        """Return preference map and full profile after a single load and schema check."""

        profile = await self.get_user_memory_profile(
            tenant_id=tenant_id, user_id=user_id
        )
        _validate_profile_schema_version(profile)
        return _preferences_dict_from_profile(profile), profile

    async def get_user_memory_profile(self, *, tenant_id: UUID, user_id: str) -> dict:
        async with self.db.get_session() as session:
            stmt = select(UserMemoryProfileModel).where(
                UserMemoryProfileModel.tenant_id == tenant_id,
                UserMemoryProfileModel.user_id == user_id,
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row is None:
                return {}
            return row.profile or {}

    async def upsert_user_preference(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        preference_key: str,
        preference_value: object,
        source: str,
    ) -> int:
        result = await self.upsert_user_preference_deterministic(
            tenant_id=tenant_id,
            user_id=user_id,
            preference_key=preference_key,
            preference_value=preference_value,
            source=source,
            source_priority_map={source: 0},
            ignore_if_unchanged=False,
        )
        return result.version

    async def upsert_user_preference_deterministic(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        preference_key: str,
        preference_value: object,
        source: str,
        source_priority_map: dict[str, int],
        ignore_if_unchanged: bool = True,
    ) -> UserPreferenceUpsertResult:
        incoming_priority = int(source_priority_map.get(source, 0))
        async with self.db.get_session() as session:
            lock_stmt = (
                select(UserMemoryProfileModel)
                .where(
                    UserMemoryProfileModel.tenant_id == tenant_id,
                    UserMemoryProfileModel.user_id == user_id,
                )
                .with_for_update()
            )
            existing_result = await session.execute(lock_stmt)
            row = existing_result.scalar_one_or_none()

            profile: dict[str, object] = (
                dict(row.profile) if row is not None and row.profile else {}
            )
            _validate_profile_schema_version(profile)
            if not profile.get("profile_schema_version"):
                profile["profile_schema_version"] = _PROFILE_SCHEMA_MIN

            prefs_raw = profile.get(_MEMORY_PREFS_KEY)
            prefs: dict[str, object] = (
                dict(prefs_raw) if type(prefs_raw) is dict else {}
            )

            existing_entry = prefs.get(preference_key)
            previous_source: str | None = None
            previous_priority = 0
            previous_version = 0
            previous_value: object | None = None
            if type(existing_entry) is dict:
                previous_source = (
                    str(existing_entry["source"])
                    if existing_entry.get("source") is not None
                    else None
                )
                previous_value = existing_entry.get("value")
                pv = existing_entry.get("version")
                if type(pv) is int:
                    previous_version = pv
                elif pv is not None:
                    try:
                        previous_version = int(pv)
                    except (TypeError, ValueError):
                        previous_version = 0
                if previous_source is not None:
                    previous_priority = int(source_priority_map.get(previous_source, 0))

            if existing_entry is None:
                prefs[preference_key] = {
                    "value": preference_value,
                    "source": source,
                    "version": 1,
                }
                profile[_MEMORY_PREFS_KEY] = prefs
                if row is None:
                    session.add(
                        UserMemoryProfileModel(
                            tenant_id=tenant_id,
                            user_id=user_id,
                            profile=profile,
                            profile_version=1,
                        )
                    )
                else:
                    row.profile = profile
                    row.profile_version = int(row.profile_version) + 1
                await session.commit()
                return UserPreferenceUpsertResult(
                    updated=True,
                    version=1,
                    previous_source=None,
                    reason="inserted",
                )

            if ignore_if_unchanged and previous_value == preference_value:
                await session.commit()
                return UserPreferenceUpsertResult(
                    updated=False,
                    version=previous_version or 1,
                    previous_source=previous_source,
                    reason="unchanged",
                )
            if incoming_priority < previous_priority:
                await session.commit()
                return UserPreferenceUpsertResult(
                    updated=False,
                    version=previous_version or 1,
                    previous_source=previous_source,
                    reason="source_priority_denied",
                )
            next_version = (previous_version or 0) + 1
            prefs[preference_key] = {
                "value": preference_value,
                "source": source,
                "version": next_version,
            }
            profile[_MEMORY_PREFS_KEY] = prefs
            row.profile = profile
            row.profile_version = int(row.profile_version) + 1
            await session.commit()
            return UserPreferenceUpsertResult(
                updated=True,
                version=next_version,
                previous_source=previous_source,
                reason="updated",
            )

    async def upsert_user_memory_profile(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        profile: dict[str, object],
    ) -> int:
        async with self.db.get_session() as session:
            stmt = (
                pg_insert(UserMemoryProfileModel)
                .values(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    profile=profile,
                    profile_version=1,
                )
                .on_conflict_do_update(
                    constraint="uq_user_memory_profile_user",
                    set_={
                        "profile": profile,
                        "profile_version": UserMemoryProfileModel.profile_version + 1,
                        "updated_at": sa.func.now(),
                    },
                )
                .returning(UserMemoryProfileModel.profile_version)
            )
            result = await session.execute(stmt)
            profile_version = int(result.scalar_one())
            await session.commit()
            return profile_version

    async def next_event_sequence(self, flow_run_id: UUID) -> int:
        async with self.db.get_session() as session:
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.repository.acquire_event_lock",
                input={"flow_run_id": str(flow_run_id)},
            ):
                await session.execute(
                    select(FlowRunLockModel)
                    .where(FlowRunLockModel.flow_run_id == flow_run_id)
                    .with_for_update()
                )
            stmt_seq = select(
                sa.func.coalesce(sa.func.max(ExecutionEventModel.event_sequence), 0)
            ).where(ExecutionEventModel.flow_run_id == flow_run_id)
            query_sql_seq = compile_query(stmt_seq)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_event_sequence",
                input={
                    "query": query_sql_seq,
                    "params": {"flow_run_id": str(flow_run_id)},
                },
                metadata={"retriever_name": "get_event_sequence"},
            ) as retriever_handle:
                result = await session.execute(stmt_seq)
                current = result.scalar_one()
                next_seq = int(current) + 1

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1,
                            "found": True,
                            "next_sequence": next_seq,
                        }
                    )

                return next_seq

    async def append_execution_event(
        self,
        *,
        tenant_id: UUID,
        user_id: str | None = None,
        session_id: UUID,
        flow_run_id: UUID,
        event_type: str,
        payload: dict,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        schema_version: int = 1,
        node_id: UUID | None = None,
        edge_id: str | None = None,
    ) -> UUID:
        event_id = uuid4()
        in_batching = False
        events_to_flush: list[dict] = []
        async with self._event_batch_lock:
            if flow_run_id in self._batching_flow_runs:
                in_batching = True
                if flow_run_id not in self._event_batch_buffer:
                    self._event_batch_buffer[flow_run_id] = []
                ev = {
                    "event_id": event_id,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "session_id": session_id,
                    "event_type": event_type,
                    "payload": payload,
                    "correlation_id": correlation_id,
                    "causation_id": causation_id,
                    "schema_version": schema_version,
                    "node_id": node_id,
                    "edge_id": edge_id,
                }
                self._event_batch_buffer[flow_run_id].append(ev)
                if len(self._event_batch_buffer[flow_run_id]) >= self._event_batch_size:
                    events_to_flush = list(self._event_batch_buffer[flow_run_id])
                    self._event_batch_buffer[flow_run_id].clear()
        if events_to_flush:
            await self._persist_execution_events_batch(flow_run_id, events_to_flush)
        if in_batching:
            return event_id
        with self.tracer.observe(
            as_type="tool",
            name="domain.execution.repository.append_execution_event",
            input={
                "flow_run_id": str(flow_run_id),
                "event_type": event_type,
                "correlation_id": str(correlation_id),
            },
        ) as tool_handle:
            async with self.db.get_session() as session:
                if user_id is None:
                    flow_run_result = await session.execute(
                        select(FlowRunModel.user_id).where(
                            FlowRunModel.flow_run_id == flow_run_id
                        )
                    )
                    user_id = flow_run_result.scalar_one_or_none()
                if user_id is None:
                    raise NotFoundServiceException(message="flow_run_user_not_found")
                await session.execute(
                    select(FlowRunLockModel)
                    .where(FlowRunLockModel.flow_run_id == flow_run_id)
                    .with_for_update()
                )
                result = await session.execute(
                    select(
                        sa.func.coalesce(
                            sa.func.max(ExecutionEventModel.event_sequence), 0
                        )
                    ).where(ExecutionEventModel.flow_run_id == flow_run_id)
                )
                next_seq = int(result.scalar_one()) + 1
                session.add(
                    ExecutionEventModel(
                        execution_event_id=event_id,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        session_id=session_id,
                        flow_run_id=flow_run_id,
                        correlation_id=correlation_id,
                        causation_id=causation_id,
                        event_sequence=next_seq,
                        schema_version=schema_version,
                        type=event_type,
                        payload=payload,
                        node_id=node_id,
                        edge_id=edge_id,
                    )
                )
                await session.commit()
                if tool_handle:
                    tool_handle.success(output={"event_id": str(event_id)})
        return event_id

    async def create_interaction(
        self,
        *,
        session_id: UUID,
        channel: str,
        payload: dict,
        headers: dict,
        metadata: dict,
        external_message_id: str | None,
        request_id: str | None,
        trace_id: str | None,
    ) -> UUID:
        interaction_id = uuid4()
        with self.tracer.observe(
            as_type="tool",
            name="domain.execution.repository.create_interaction",
            input={
                "interaction_id": str(interaction_id),
                "session_id": str(session_id),
            },
        ) as tool_handle:
            async with self.db.get_session() as session:
                session.add(
                    InteractionModel(
                        interaction_id=interaction_id,
                        session_id=session_id,
                        channel=channel,
                        payload=payload,
                        output={},
                        headers=headers,
                        interaction_metadata=metadata,
                        result_node_run_id=None,
                        external_message_id=external_message_id,
                        request_id=request_id,
                        trace_id=trace_id,
                    )
                )
                await session.commit()
                if tool_handle:
                    tool_handle.success(output={"interaction_id": str(interaction_id)})
        return interaction_id

    async def link_interaction_to_flow_run(
        self, *, interaction_id: UUID, flow_run_id: UUID
    ) -> None:
        async with self.db.get_session() as session:
            stmt_int = select(InteractionModel).where(
                InteractionModel.interaction_id == interaction_id
            )
            query_sql_int = compile_query(stmt_int)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_interaction_for_link",
                input={
                    "query": query_sql_int,
                    "params": {"interaction_id": str(interaction_id)},
                },
                metadata={"retriever_name": "get_interaction_for_link"},
            ) as retriever_handle:
                result = await session.execute(stmt_int)
                instance = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if instance else 0,
                            "found": instance is not None,
                        }
                    )

            if instance is None:
                raise NotFoundServiceException(message="interaction_not_found")
            instance.flow_run_id = flow_run_id
            await session.execute(
                sa.update(FlowRunModel)
                .where(FlowRunModel.flow_run_id == flow_run_id)
                .values(interaction_id=interaction_id)
            )
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.repository.link_interaction_to_flow_run",
                input={
                    "interaction_id": str(interaction_id),
                    "flow_run_id": str(flow_run_id),
                },
            ) as tool_handle:
                await session.commit()
                if tool_handle:
                    tool_handle.success(
                        output={
                            "interaction_id": str(interaction_id),
                            "flow_run_id": str(flow_run_id),
                        }
                    )

    async def set_current_interaction_result_for_flow_run(
        self,
        *,
        flow_run_id: UUID,
        output: dict,
        result_node_run_id: UUID | None,
    ) -> None:
        with self.tracer.observe(
            as_type="tool",
            name="domain.execution.repository.set_current_interaction_result_for_flow_run",
            input={"flow_run_id": str(flow_run_id)},
        ) as tool_handle:
            async with self.db.get_session() as session:
                interaction_id_subq = (
                    select(FlowRunModel.interaction_id)
                    .where(FlowRunModel.flow_run_id == flow_run_id)
                    .scalar_subquery()
                )
                await session.execute(
                    sa.update(InteractionModel)
                    .where(InteractionModel.interaction_id == interaction_id_subq)
                    .values(
                        output=output or {},
                        result_node_run_id=result_node_run_id,
                        completed_at=sa.func.now(),
                    )
                )
                if tool_handle:
                    tool_handle.success(
                        output={
                            "flow_run_id": str(flow_run_id),
                            "output": output,
                            "result_node_run_id": str(result_node_run_id),
                        }
                    )
                await session.commit()

    async def get_flow_run(self, flow_run_id: UUID) -> FlowRunModel | None:
        async with self.db.get_session() as session:
            stmt = select(FlowRunModel).where(FlowRunModel.flow_run_id == flow_run_id)
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_flow_run",
                input={
                    "query": query_sql,
                    "params": {"flow_run_id": str(flow_run_id)},
                },
                metadata={"retriever_name": "get_flow_run"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                flow_run = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if flow_run else 0,
                            "found": flow_run is not None,
                        }
                    )

                return flow_run

    async def get_latest_waiting_flow_run_id(
        self,
        *,
        session_id: UUID,
        correlation_id: UUID,
        flow_version_id: UUID,
        user_id: str,
    ) -> tuple[UUID | None, list[UUID]]:
        async with self.db.get_session() as session:
            stmt = (
                select(FlowRunModel.flow_run_id)
                .where(FlowRunModel.session_id == session_id)
                .where(FlowRunModel.correlation_id == correlation_id)
                .where(FlowRunModel.flow_version_id == flow_version_id)
                .where(FlowRunModel.user_id == user_id)
                .where(
                    sa.or_(
                        FlowRunModel.status == RunStatus.WAITING_INPUT,
                        FlowRunModel.canonical_status == FlowRunStatus.WAITING,
                    )
                )
                .order_by(
                    FlowRunModel.created_at.desc(),
                    FlowRunModel.flow_run_id.desc(),
                )
                .limit(2)
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_latest_waiting_flow_run_id",
                input={
                    "query": query_sql,
                    "params": {
                        "session_id": str(session_id),
                        "correlation_id": str(correlation_id),
                        "flow_version_id": str(flow_version_id),
                        "user_id": user_id,
                    },
                },
                metadata={"retriever_name": "get_latest_waiting_flow_run_id"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                candidates = list(result.scalars().all())

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": len(candidates),
                            "found": len(candidates) > 0,
                        }
                    )

                origin_id = candidates[0] if candidates else None
                return origin_id, candidates

    async def get_tool_run(self, tool_run_id: UUID) -> ToolRunModel | None:
        async with self.db.get_session() as session:
            stmt = select(ToolRunModel).where(ToolRunModel.tool_run_id == tool_run_id)
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_tool_run",
                input={
                    "query": query_sql,
                    "params": {"tool_run_id": str(tool_run_id)},
                },
                metadata={"retriever_name": "get_tool_run"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                tool_run = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if tool_run else 0,
                            "found": tool_run is not None,
                        }
                    )

                return tool_run

    async def get_active_billing_policy_version_id(
        self, tenant_id: UUID
    ) -> UUID | None:
        key = f"active_billing_version:{tenant_id}"
        if cached := await self.cache_adapter.get(key):
            if isinstance(cached, dict) and cached.get("billing_policy_version_id"):
                return UUID(cached["billing_policy_version_id"])
        async with self.db.get_session() as session:
            stmt = select(BillingPolicyVersionModel.billing_policy_version_id).where(
                BillingPolicyVersionModel.tenant_id == tenant_id,
                BillingPolicyVersionModel.is_active.is_(True),
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_active_billing_policy_version_id",
                input={
                    "query": query_sql,
                    "params": {"tenant_id": str(tenant_id)},
                },
                metadata={
                    "retriever_name": "get_active_billing_policy_version_id",
                },
            ) as retriever_handle:
                result = await session.execute(stmt)
                version_id = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if version_id else 0,
                            "found": version_id is not None,
                        }
                    )

        if version_id is None:
            return None
        await self.cache_adapter.set(
            key, {"billing_policy_version_id": str(version_id)}
        )
        return version_id

    async def get_billing_policy_version(
        self, billing_policy_version_id: UUID
    ) -> BillingPolicyVersionModel | None:
        key = f"billing_policy_version:{billing_policy_version_id}"
        if cached := await self.cache_adapter.get(key):
            return BillingPolicyVersionModel.from_dict(cached)
        async with self.db.get_session() as session:
            stmt = select(BillingPolicyVersionModel).where(
                BillingPolicyVersionModel.billing_policy_version_id
                == billing_policy_version_id
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_billing_policy_version",
                input={
                    "query": query_sql,
                    "params": {
                        "billing_policy_version_id": str(billing_policy_version_id),
                    },
                },
                metadata={"retriever_name": "get_billing_policy_version"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                policy = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if policy else 0,
                            "found": policy is not None,
                        }
                    )

        if policy is None:
            return None
        await self.cache_adapter.set(key, policy.to_dict())
        return policy

    async def get_active_memory_policy_version_id(self, tenant_id: UUID) -> UUID | None:
        key = f"active_memory_version:{tenant_id}"
        if cached := await self.cache_adapter.get(key):
            if isinstance(cached, dict) and cached.get("memory_policy_version_id"):
                return UUID(cached["memory_policy_version_id"])
        async with self.db.get_session() as session:
            stmt = select(MemoryPolicyVersionModel.memory_policy_version_id).where(
                MemoryPolicyVersionModel.tenant_id == tenant_id,
                MemoryPolicyVersionModel.is_active.is_(True),
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_active_memory_policy_version_id",
                input={
                    "query": query_sql,
                    "params": {"tenant_id": str(tenant_id)},
                },
                metadata={
                    "retriever_name": "get_active_memory_policy_version_id",
                },
            ) as retriever_handle:
                result = await session.execute(stmt)
                version_id = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if version_id else 0,
                            "found": version_id is not None,
                        }
                    )

        if version_id is None:
            return None
        await self.cache_adapter.set(key, {"memory_policy_version_id": str(version_id)})
        return version_id

    async def get_memory_policy_version(
        self, memory_policy_version_id: UUID
    ) -> MemoryPolicyVersionModel | None:
        key = f"memory_policy_version:{memory_policy_version_id}"
        if cached := await self.cache_adapter.get(key):
            return MemoryPolicyVersionModel.from_dict(cached)
        async with self.db.get_session() as session:
            stmt = select(MemoryPolicyVersionModel).where(
                MemoryPolicyVersionModel.memory_policy_version_id
                == memory_policy_version_id
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_memory_policy_version",
                input={
                    "query": query_sql,
                    "params": {
                        "memory_policy_version_id": str(memory_policy_version_id),
                    },
                },
                metadata={"retriever_name": "get_memory_policy_version"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                policy = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if policy else 0,
                            "found": policy is not None,
                        }
                    )

        if policy is None:
            return None
        await self.cache_adapter.set(key, policy.to_dict())
        return policy

    async def get_active_rag_policy_version_id(self, tenant_id: UUID) -> UUID | None:
        key = f"active_rag_version:{tenant_id}"
        if cached := await self.cache_adapter.get(key):
            if isinstance(cached, dict) and cached.get("rag_policy_version_id"):
                return UUID(cached["rag_policy_version_id"])
        async with self.db.get_session() as session:
            stmt = select(RagPolicyVersionModel.rag_policy_version_id).where(
                RagPolicyVersionModel.tenant_id == tenant_id,
                RagPolicyVersionModel.is_active.is_(True),
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_active_rag_policy_version_id",
                input={
                    "query": query_sql,
                    "params": {"tenant_id": str(tenant_id)},
                },
                metadata={
                    "retriever_name": "get_active_rag_policy_version_id",
                },
            ) as retriever_handle:
                result = await session.execute(stmt)
                version_id = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if version_id else 0,
                            "found": version_id is not None,
                        }
                    )

        if version_id is None:
            return None
        await self.cache_adapter.set(key, {"rag_policy_version_id": str(version_id)})
        return version_id

    async def get_rag_policy_version(
        self, rag_policy_version_id: UUID
    ) -> RagPolicyVersionModel | None:
        key = f"rag_policy_version:{rag_policy_version_id}"
        if cached := await self.cache_adapter.get(key):
            return RagPolicyVersionModel.from_dict(cached)
        async with self.db.get_session() as session:
            stmt = select(RagPolicyVersionModel).where(
                RagPolicyVersionModel.rag_policy_version_id == rag_policy_version_id
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_rag_policy_version",
                input={
                    "query": query_sql,
                    "params": {
                        "rag_policy_version_id": str(rag_policy_version_id),
                    },
                },
                metadata={"retriever_name": "get_rag_policy_version"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                policy = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if policy else 0,
                            "found": policy is not None,
                        }
                    )

        if policy is None:
            return None
        await self.cache_adapter.set(key, policy.to_dict())
        return policy

    async def stamp_agent_run_billing_policy(
        self, *, agent_run_id: UUID, billing_policy_version_id: UUID
    ) -> None:
        async with self.db.get_session() as session:
            stmt_ar = select(AgentRunModel).where(
                AgentRunModel.agent_run_id == agent_run_id
            )
            query_sql_ar = compile_query(stmt_ar)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_agent_run_for_billing",
                input={
                    "query": query_sql_ar,
                    "params": {"agent_run_id": str(agent_run_id)},
                },
                metadata={"retriever_name": "get_agent_run_for_billing"},
            ) as retriever_handle:
                result = await session.execute(stmt_ar)
                instance = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if instance else 0,
                            "found": instance is not None,
                        }
                    )

            if instance is None:
                raise NotFoundServiceException(message="agent_run_not_found")
            instance.billing_policy_version_id = billing_policy_version_id
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.repository.stamp_agent_run_billing_policy",
                input={
                    "agent_run_id": str(agent_run_id),
                    "billing_policy_version_id": str(billing_policy_version_id),
                },
            ):
                await session.commit()

    async def stamp_tool_run_billing_policy(
        self,
        *,
        tool_run_id: UUID,
        billing_policy_version_id: UUID,
        estimated_cost: float | None = None,
    ) -> None:
        async with self.db.get_session() as session:
            stmt_tr = select(ToolRunModel).where(
                ToolRunModel.tool_run_id == tool_run_id
            )
            query_sql_tr = compile_query(stmt_tr)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_tool_run_for_billing",
                input={
                    "query": query_sql_tr,
                    "params": {"tool_run_id": str(tool_run_id)},
                },
                metadata={"retriever_name": "get_tool_run_for_billing"},
            ) as retriever_handle:
                result = await session.execute(stmt_tr)
                instance = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if instance else 0,
                            "found": instance is not None,
                        }
                    )

            if instance is None:
                raise NotFoundServiceException(message="tool_run_not_found")
            instance.billing_policy_version_id = billing_policy_version_id
            if estimated_cost is not None:
                instance.estimated_cost = estimated_cost
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.repository.stamp_tool_run_billing_policy",
                input={
                    "tool_run_id": str(tool_run_id),
                    "billing_policy_version_id": str(billing_policy_version_id),
                },
            ):
                await session.commit()

    async def list_execution_events(
        self,
        *,
        flow_run_id: UUID | None = None,
        correlation_id: UUID | None = None,
        limit: int = 200,
    ) -> list[ExecutionEventModel]:
        async with self.db.get_session() as session:
            stmt = select(ExecutionEventModel)
            if flow_run_id is not None:
                stmt = stmt.where(ExecutionEventModel.flow_run_id == flow_run_id)
            if correlation_id is not None:
                stmt = stmt.where(ExecutionEventModel.correlation_id == correlation_id)
            stmt = stmt.order_by(
                ExecutionEventModel.flow_run_id,
                ExecutionEventModel.event_sequence,
            ).limit(limit)
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.list_execution_events",
                input={
                    "query": query_sql,
                    "params": {
                        "flow_run_id": str(flow_run_id) if flow_run_id else None,
                        "correlation_id": (
                            str(correlation_id) if correlation_id else None
                        ),
                        "limit": limit,
                    },
                },
                metadata={"retriever_name": "list_execution_events"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                events = list(result.scalars().all())

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": len(events),
                            "found": len(events) > 0,
                        }
                    )

                return events

    async def count_tool_runs_for_flow_run(self, flow_run_id: UUID) -> int:
        async with self.db.get_session() as session:
            node_run_direct = aliased(NodeRunModel)
            node_run_via_agent = aliased(NodeRunModel)
            stmt = (
                select(sa.func.count(sa.distinct(ToolRunModel.tool_run_id)))
                .select_from(ToolRunModel)
                .outerjoin(
                    node_run_direct,
                    ToolRunModel.node_run_id == node_run_direct.node_run_id,
                )
                .outerjoin(
                    AgentRunModel,
                    ToolRunModel.agent_run_id == AgentRunModel.agent_run_id,
                )
                .outerjoin(
                    node_run_via_agent,
                    AgentRunModel.node_run_id == node_run_via_agent.node_run_id,
                )
                .where(
                    sa.or_(
                        node_run_direct.flow_run_id == flow_run_id,
                        node_run_via_agent.flow_run_id == flow_run_id,
                    )
                )
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.count_tool_runs_for_flow_run",
                input={
                    "query": query_sql,
                    "params": {"flow_run_id": str(flow_run_id)},
                },
                metadata={"retriever_name": "count_tool_runs_for_flow_run"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                count = int(result.scalar_one() or 0)

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1,
                            "found": count > 0,
                            "count": count,
                        }
                    )

                return count

    async def count_agent_runs_for_flow_run(self, flow_run_id: UUID) -> int:
        async with self.db.get_session() as session:
            stmt = (
                select(sa.func.count(sa.distinct(AgentRunModel.agent_run_id)))
                .select_from(AgentRunModel)
                .join(
                    NodeRunModel,
                    AgentRunModel.node_run_id == NodeRunModel.node_run_id,
                )
                .where(NodeRunModel.flow_run_id == flow_run_id)
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.count_agent_runs_for_flow_run",
                input={
                    "query": query_sql,
                    "params": {"flow_run_id": str(flow_run_id)},
                },
                metadata={"retriever_name": "count_agent_runs_for_flow_run"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                count = int(result.scalar_one() or 0)

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1,
                            "found": count > 0,
                            "count": count,
                        }
                    )

                return count

    async def update_tool_run_result(
        self,
        *,
        tool_run_id: UUID,
        status: str,
        canonical_status: str,
        output: dict | None,
        error: dict | None,
    ) -> None:
        async with self.db.get_session() as session:
            stmt_tr = select(ToolRunModel).where(
                ToolRunModel.tool_run_id == tool_run_id
            )
            query_sql_tr = compile_query(stmt_tr)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_tool_run_for_result",
                input={
                    "query": query_sql_tr,
                    "params": {"tool_run_id": str(tool_run_id)},
                },
                metadata={"retriever_name": "get_tool_run_for_result"},
            ) as retriever_handle:
                result = await session.execute(stmt_tr)
                instance = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if instance else 0,
                            "found": instance is not None,
                        }
                    )

            if instance is None:
                raise NotFoundServiceException(message="tool_run_not_found")
            instance.status = status
            instance.canonical_status = str(canonical_status)
            instance.output = output or {}
            instance.error = error or {}
            if status in (ToolRunStatus.SUCCESS, ToolRunStatus.ERROR):
                instance.finished_at = sa.func.now()
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.repository.update_tool_run_result",
                input={
                    "tool_run_id": str(tool_run_id),
                    "status": status,
                    "canonical_status": canonical_status,
                    "output": output,
                    "error": error,
                },
            ) as tool_handle:
                await session.commit()
                if tool_handle:
                    tool_handle.success(
                        output={
                            "tool_run_id": str(tool_run_id),
                            "status": status,
                            "canonical_status": canonical_status,
                            "output": output,
                            "error": error,
                        }
                    )

    async def get_flow_run_id_for_tool_run(self, tool_run_id: UUID) -> UUID:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.repository.get_flow_run_id_for_tool_run",
            input={"tool_run_id": str(tool_run_id)},
        ) as handle:
            tool_run = await self.get_tool_run(tool_run_id)
            if tool_run is None:
                raise NotFoundServiceException(message="tool_run_not_found")
            if tool_run.node_run_id:
                node_run = await self.get_node_run(tool_run.node_run_id)
                if node_run is None:
                    raise NotFoundServiceException(message="node_run_not_found")
                if handle:
                    handle.success(output={"flow_run_id": str(node_run.flow_run_id)})
                return node_run.flow_run_id
            if tool_run.agent_run_id:
                agent_run = await self.get_agent_run(tool_run.agent_run_id)
                if agent_run is None:
                    raise NotFoundServiceException(message="agent_run_not_found")
                node_run = await self.get_node_run(agent_run.node_run_id)
                if node_run is None:
                    raise NotFoundServiceException(message="node_run_not_found")
                if handle:
                    handle.success(output={"flow_run_id": str(node_run.flow_run_id)})
                return node_run.flow_run_id
            raise DomainValidationException(message="tool_run_missing_parent")

    async def create_run_failure_for_tool_run(
        self,
        *,
        tool_run_id: UUID,
        correlation_id: UUID,
        error_type: str,
        error: dict,
    ) -> UUID:
        run_failure_id = uuid4()
        async with self.db.get_session() as session:
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.repository.create_run_failure_for_tool_run",
                input={
                    "tool_run_id": str(tool_run_id),
                    "correlation_id": str(correlation_id),
                },
            ):
                session.add(
                    RunFailureModel(
                        run_failure_id=run_failure_id,
                        tool_run_id=tool_run_id,
                        error_type=error_type,
                        error=error,
                        correlation_id=correlation_id,
                    )
                )
            await session.commit()
        return run_failure_id

    async def create_response_artifact_for_tool_run(
        self, *, tool_run_id: UUID, payload: dict
    ) -> UUID:
        with self.tracer.observe(
            as_type="retriever",
            name="domain.execution.repository.get_flow_run_for_artifact",
            input={"tool_run_id": str(tool_run_id)},
        ) as handle:
            flow_run_id = await self.get_flow_run_id_for_tool_run(tool_run_id)
            flow_run = await self.get_flow_run(flow_run_id)
            if handle:
                handle.success(
                    output={
                        "result_count": 1,
                        "found": flow_run is not None,
                        "flow_run_id": str(flow_run_id),
                    }
                )
        if flow_run is None or flow_run.interaction_id is None:
            raise DomainValidationException(message="flow_run_missing_interaction")

        response_artifact_id = uuid4()
        async with self.db.get_session() as session:
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.repository.create_response_artifact",
                input={
                    "tool_run_id": str(tool_run_id),
                    "flow_run_id": str(flow_run_id),
                },
            ) as tool_handle:
                session.add(
                    ResponseArtifactModel(
                        response_artifact_id=response_artifact_id,
                        interaction_id=flow_run.interaction_id,
                        flow_run_id=flow_run_id,
                        payload=payload,
                        schema_version=1,
                    )
                )
            await session.commit()
            if tool_handle:
                tool_handle.success(
                    output={"response_artifact_id": str(response_artifact_id)}
                )
        return response_artifact_id

    async def create_response_artifact_for_flow_run(
        self, *, flow_run_id: UUID, payload: dict
    ) -> UUID:
        flow_run = await self.get_flow_run(flow_run_id)
        if flow_run is None or flow_run.interaction_id is None:
            raise DomainValidationException(message="flow_run_missing_interaction")

        response_artifact_id = uuid4()
        async with self.db.get_session() as session:
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.repository.create_response_artifact_for_flow_run",
                input={"flow_run_id": str(flow_run_id)},
            ) as tool_handle:
                session.add(
                    ResponseArtifactModel(
                        response_artifact_id=response_artifact_id,
                        interaction_id=flow_run.interaction_id,
                        flow_run_id=flow_run_id,
                        payload=payload,
                        schema_version=1,
                    )
                )
            await session.commit()
            if tool_handle:
                tool_handle.success(
                    output={"response_artifact_id": str(response_artifact_id)}
                )
        return response_artifact_id

    async def create_tool_run(
        self,
        *,
        tool_config_id: UUID,
        correlation_id: UUID,
        agent_run_id: UUID | None,
        node_run_id: UUID | None,
        idempotency_key: str | None,
        has_side_effect: bool,
        input_payload: dict,
        estimated_cost: float | None = None,
        billing_policy_version_id: UUID | None = None,
    ) -> UUID:
        tool_run_id = uuid4()
        async with self.db.get_session() as session:
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.repository.create_tool_run",
                input={
                    "tool_config_id": str(tool_config_id),
                    "correlation_id": str(correlation_id),
                },
            ) as tool_handle:
                session.add(
                    ToolRunModel(
                        tool_run_id=tool_run_id,
                        tool_config_id=tool_config_id,
                        correlation_id=correlation_id,
                        agent_run_id=agent_run_id,
                        node_run_id=node_run_id,
                        idempotency_key=idempotency_key,
                        has_side_effect=has_side_effect,
                        input=input_payload,
                        estimated_cost=estimated_cost,
                        billing_policy_version_id=billing_policy_version_id,
                    )
                )
            await session.commit()
            if tool_handle:
                tool_handle.success(output={"tool_run_id": str(tool_run_id)})
        return tool_run_id

    async def create_node_run(
        self,
        *,
        flow_run_id: UUID,
        node_id: UUID,
        correlation_id: UUID,
        input_payload: dict,
        output_payload: dict,
        status: str,
        canonical_status: str,
    ) -> UUID:
        node_run_id = uuid4()
        async with self.db.get_session() as session:
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.repository.create_node_run",
                input={
                    "flow_run_id": str(flow_run_id),
                    "node_id": str(node_id),
                    "correlation_id": str(correlation_id),
                },
            ) as tool_handle:
                session.add(
                    NodeRunModel(
                        node_run_id=node_run_id,
                        flow_run_id=flow_run_id,
                        node_id=node_id,
                        correlation_id=correlation_id,
                        input=input_payload,
                        output=output_payload,
                        status=status,
                        canonical_status=canonical_status,
                    )
                )
            await session.commit()
            if tool_handle:
                tool_handle.success(output={"node_run_id": str(node_run_id)})
                return node_run_id
            raise DomainValidationException(message="node_run_not_created")

    async def update_node_run_result(
        self,
        *,
        node_run_id: UUID,
        output_payload: dict,
        status: str,
        canonical_status: str,
    ) -> None:
        async with self.db.get_session() as session:
            stmt_nr = select(NodeRunModel).where(
                NodeRunModel.node_run_id == node_run_id
            )
            query_sql_nr = compile_query(stmt_nr)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_node_run_for_result",
                input={
                    "query": query_sql_nr,
                    "params": {"node_run_id": str(node_run_id)},
                },
                metadata={"retriever_name": "get_node_run_for_result"},
            ) as retriever_handle:
                result = await session.execute(stmt_nr)
                instance = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if instance else 0,
                            "found": instance is not None,
                        }
                    )

            if instance is None:
                raise NotFoundServiceException(message="node_run_not_found")
            instance.output = output_payload
            instance.status = status
            instance.canonical_status = canonical_status
            instance.finished_at = sa.func.now()
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.repository.update_node_run_result",
                input={"node_run_id": str(node_run_id), "status": status},
            ) as tool_handle:
                await session.commit()
            if tool_handle:
                tool_handle.success(
                    output={"node_run_id": str(node_run_id), "status": status}
                )

    async def get_graph_state(self, flow_run_id: UUID) -> GraphStateModel | None:
        key = f"graph_state:{flow_run_id}"
        if cached := await self.cache_adapter.get(key):
            return GraphStateModel.from_dict(cached)
        async with self.db.get_session() as session:
            stmt = select(GraphStateModel).where(
                GraphStateModel.flow_run_id == flow_run_id
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_graph_state",
                input={
                    "query": query_sql,
                    "params": {"flow_run_id": str(flow_run_id)},
                },
                metadata={"retriever_name": "get_graph_state"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                state = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if state else 0,
                            "found": state is not None,
                        }
                    )

                if state:
                    await self.cache_adapter.set(key, state.to_dict(), ttl=60)
                return state

    async def upsert_graph_state(
        self,
        *,
        flow_run_id: UUID,
        state: dict,
        last_node_run_id: UUID | None,
    ) -> None:
        async with self.db.get_session() as session:
            stmt_gs = select(GraphStateModel).where(
                GraphStateModel.flow_run_id == flow_run_id
            )
            query_sql_gs = compile_query(stmt_gs)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_graph_state_for_upsert",
                input={
                    "query": query_sql_gs,
                    "params": {"flow_run_id": str(flow_run_id)},
                },
                metadata={"retriever_name": "get_graph_state_for_upsert"},
            ) as retriever_handle:
                result = await session.execute(stmt_gs)
                instance = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if instance else 0,
                            "found": instance is not None,
                        }
                    )

            if instance is None:
                session.add(
                    GraphStateModel(
                        flow_run_id=flow_run_id,
                        state=state,
                        last_node_run_id=last_node_run_id,
                    )
                )
            else:
                instance.state = state
                instance.last_node_run_id = last_node_run_id
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.repository.upsert_graph_state",
                input={"flow_run_id": str(flow_run_id)},
            ) as tool_handle:
                if tool_handle:
                    tool_handle.success(
                        output={
                            "flow_run_id": str(flow_run_id),
                            "state": state,
                            "last_node_run_id": last_node_run_id,
                        }
                    )
                await session.commit()
                await self.cache_adapter.delete(f"graph_state:{flow_run_id}")

    async def get_flow_version(self, flow_version_id: UUID) -> FlowVersionModel | None:
        key = f"flow_version:{flow_version_id}"
        if cached := await self.cache_adapter.get(key):
            return FlowVersionModel.from_dict(cached)
        async with self.db.get_session() as session:
            stmt = select(FlowVersionModel).where(
                FlowVersionModel.flow_version_id == flow_version_id
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_flow_version",
                input={
                    "query": query_sql,
                    "params": {"flow_version_id": str(flow_version_id)},
                },
                metadata={"retriever_name": "get_flow_version"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                version = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if version else 0,
                            "found": version is not None,
                        }
                    )

        if version is None:
            return None
        await self.cache_adapter.set(key, version.to_dict())
        return version

    async def get_flow(self, flow_id: UUID) -> FlowModel | None:
        async with self.db.get_session() as session:
            stmt = select(FlowModel).where(FlowModel.flow_id == flow_id)
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_flow",
                input={"query": query_sql, "params": {"flow_id": str(flow_id)}},
                metadata={"retriever_name": "get_flow"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                flow = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if flow else 0,
                            "found": flow is not None,
                        }
                    )
        return flow

    async def get_active_flow_version_id(self, flow_id: UUID) -> UUID | None:
        key = f"flow_active_version:{flow_id}"
        if cached := await self.cache_adapter.get(key):
            if isinstance(cached, dict) and cached.get("flow_version_id"):
                return UUID(cached["flow_version_id"])
        async with self.db.get_session() as session:
            stmt = select(FlowVersionModel.flow_version_id).where(
                FlowVersionModel.flow_id == flow_id,
                FlowVersionModel.is_active.is_(True),
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_active_flow_version_id",
                input={"query": query_sql, "params": {"flow_id": str(flow_id)}},
                metadata={"retriever_name": "get_active_flow_version_id"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                version_id = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if version_id else 0,
                            "found": version_id is not None,
                        }
                    )

        if version_id is None:
            return None
        await self.cache_adapter.set(key, {"flow_version_id": str(version_id)})
        return version_id

    async def get_flow_graph_by_flow_version(
        self, flow_version_id: UUID
    ) -> FlowGraphModel | None:
        key = f"flow_graph:{flow_version_id}"
        if cached := await self.cache_adapter.get(key):
            return FlowGraphModel.from_dict(cached)
        async with self.db.get_session() as session:
            stmt = select(FlowGraphModel).where(
                FlowGraphModel.flow_version_id == flow_version_id
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_flow_graph_by_flow_version",
                input={
                    "query": query_sql,
                    "params": {"flow_version_id": str(flow_version_id)},
                },
                metadata={"retriever_name": "get_flow_graph_by_flow_version"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                graph = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if graph else 0,
                            "found": graph is not None,
                        }
                    )

        if graph is None:
            return None
        await self.cache_adapter.set(key, graph.to_dict())
        return graph

    async def get_flow_graph_snapshot_by_flow_version(
        self, flow_version_id: UUID
    ) -> FlowGraphSnapshotModel | None:
        key = f"flow_snapshot:{flow_version_id}"
        if cached := await self.cache_adapter.get(key):
            return FlowGraphSnapshotModel.from_dict(cached)
        async with self.db.get_session() as session:
            stmt = select(FlowGraphSnapshotModel).where(
                FlowGraphSnapshotModel.flow_version_id == flow_version_id
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_flow_graph_snapshot",
                input={
                    "query": query_sql,
                    "params": {"flow_version_id": str(flow_version_id)},
                },
                metadata={"retriever_name": "get_flow_graph_snapshot"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                snapshot = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if snapshot else 0,
                            "found": snapshot is not None,
                        }
                    )

        if snapshot is None:
            return None
        await self.cache_adapter.set(key, snapshot.to_dict())
        return snapshot

    async def get_flow_graph_snapshot(
        self, flow_graph_snapshot_id: UUID
    ) -> FlowGraphSnapshotModel | None:
        async with self.db.get_session() as session:
            stmt = select(FlowGraphSnapshotModel).where(
                FlowGraphSnapshotModel.flow_graph_snapshot_id == flow_graph_snapshot_id
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_tool_config(self, tool_config_id: UUID) -> ToolConfigModel | None:
        key = f"tool_config:{tool_config_id}"
        if cached := await self.cache_adapter.get(key):
            return ToolConfigModel.from_dict(cached)
        async with self.db.get_session() as session:
            stmt = select(ToolConfigModel).where(
                ToolConfigModel.tool_config_id == tool_config_id
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_tool_config",
                input={
                    "query": query_sql,
                    "params": {"tool_config_id": str(tool_config_id)},
                },
                metadata={"retriever_name": "get_tool_config"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                tool_config = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if tool_config else 0,
                            "found": tool_config is not None,
                        }
                    )

        if tool_config is None:
            return None
        await self.cache_adapter.set(key, tool_config.to_dict())
        return tool_config

    async def get_agent_run(self, agent_run_id: UUID) -> AgentRunModel | None:
        async with self.db.get_session() as session:
            stmt = select(AgentRunModel).where(
                AgentRunModel.agent_run_id == agent_run_id
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_agent_run",
                input={
                    "query": query_sql,
                    "params": {"agent_run_id": str(agent_run_id)},
                },
                metadata={"retriever_name": "get_agent_run"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                run = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if run else 0,
                            "found": run is not None,
                        }
                    )

                return run

    async def get_agent_run_by_agent_version_and_flow(
        self, agent_version_id: UUID, flow_run_id: UUID
    ) -> AgentRunModel | None:
        async with self.db.get_session() as session:
            stmt = (
                select(AgentRunModel)
                .join(
                    NodeRunModel,
                    AgentRunModel.node_run_id == NodeRunModel.node_run_id,
                )
                .where(
                    AgentRunModel.agent_version_id == agent_version_id,
                    NodeRunModel.flow_run_id == flow_run_id,
                )
                .order_by(AgentRunModel.created_at.desc())
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_agent_run_by_version_and_flow",
                input={
                    "query": query_sql,
                    "params": {
                        "agent_version_id": str(agent_version_id),
                        "flow_run_id": str(flow_run_id),
                    },
                },
                metadata={
                    "retriever_name": "get_agent_run_by_agent_version_and_flow",
                },
            ) as retriever_handle:
                result = await session.execute(stmt)
                run = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if run else 0,
                            "found": run is not None,
                        }
                    )

                return run

    async def get_agent_version(
        self, agent_version_id: UUID
    ) -> AgentVersionModel | None:
        key = f"agent_version:{agent_version_id}"
        if cached := await self.cache_adapter.get(key):
            return AgentVersionModel.from_dict(cached)
        async with self.db.get_session() as session:
            stmt = select(AgentVersionModel).where(
                AgentVersionModel.agent_version_id == agent_version_id
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_agent_version",
                input={
                    "query": query_sql,
                    "params": {"agent_version_id": str(agent_version_id)},
                },
                metadata={"retriever_name": "get_agent_version"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                version = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if version else 0,
                            "found": version is not None,
                        }
                    )

        if version is None:
            return None
        await self.cache_adapter.set(key, version.to_dict())
        return version

    async def get_active_agent_version_id(self, agent_id: UUID) -> UUID | None:
        key = f"agent_active_version:{agent_id}"
        if cached := await self.cache_adapter.get(key):
            if isinstance(cached, dict) and cached.get("agent_version_id"):
                return UUID(cached["agent_version_id"])
        async with self.db.get_session() as session:
            stmt = select(AgentVersionModel.agent_version_id).where(
                AgentVersionModel.agent_id == agent_id,
                AgentVersionModel.is_active.is_(True),
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_active_agent_version_id",
                input={"query": query_sql, "params": {"agent_id": str(agent_id)}},
                metadata={"retriever_name": "get_active_agent_version_id"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                version_id = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if version_id else 0,
                            "found": version_id is not None,
                        }
                    )

        if version_id is None:
            return None
        await self.cache_adapter.set(key, {"agent_version_id": str(version_id)})
        return version_id

    async def get_ai_execution_policy_version(
        self, ai_execution_policy_version_id: UUID
    ) -> AIExecutionPolicyVersionModel | None:
        key = f"ai_policy_version:{ai_execution_policy_version_id}"
        if cached := await self.cache_adapter.get(key):
            return AIExecutionPolicyVersionModel.from_dict(cached)
        async with self.db.get_session() as session:
            stmt = select(AIExecutionPolicyVersionModel).where(
                AIExecutionPolicyVersionModel.ai_execution_policy_version_id
                == ai_execution_policy_version_id
            )
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_ai_execution_policy_version",
                input={
                    "query": query_sql,
                    "params": {
                        "ai_execution_policy_version_id": str(
                            ai_execution_policy_version_id
                        ),
                    },
                },
                metadata={
                    "retriever_name": "get_ai_execution_policy_version",
                },
            ) as retriever_handle:
                result = await session.execute(stmt)
                policy = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if policy else 0,
                            "found": policy is not None,
                        }
                    )

        if policy is None:
            return None
        await self.cache_adapter.set(key, policy.to_dict())
        return policy

    async def get_model(self, model_id: UUID) -> ModelModel | None:
        key = f"model:{model_id}"
        if cached := await self.cache_adapter.get(key):
            return ModelModel.from_dict(cached)
        async with self.db.get_session() as session:
            stmt = select(ModelModel).where(ModelModel.model_id == model_id)
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_model",
                input={"query": query_sql, "params": {"model_id": str(model_id)}},
                metadata={"retriever_name": "get_model"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                model = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if model else 0,
                            "found": model is not None,
                        }
                    )

        if model is None:
            return None
        await self.cache_adapter.set(key, model.to_dict())
        return model

    async def get_node_run(self, node_run_id: UUID) -> NodeRunModel | None:
        async with self.db.get_session() as session:
            stmt = select(NodeRunModel).where(NodeRunModel.node_run_id == node_run_id)
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_node_run",
                input={
                    "query": query_sql,
                    "params": {"node_run_id": str(node_run_id)},
                },
                metadata={"retriever_name": "get_node_run"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                run = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if run else 0,
                            "found": run is not None,
                        }
                    )

                return run

    async def get_node(self, node_id: UUID) -> NodeModel | None:
        key = f"node:{node_id}"
        if cached := await self.cache_adapter.get(key):
            return NodeModel.from_dict(cached)
        async with self.db.get_session() as session:
            stmt = select(NodeModel).where(NodeModel.node_id == node_id)
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_node",
                input={"query": query_sql, "params": {"node_id": str(node_id)}},
                metadata={"retriever_name": "get_node"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                node = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if node else 0,
                            "found": node is not None,
                        }
                    )

        if node is None:
            return None
        await self.cache_adapter.set(key, node.to_dict())
        return node

    async def create_agent_run(
        self,
        *,
        node_run_id: UUID,
        agent_version_id: UUID,
        correlation_id: UUID,
        input_payload: dict,
        model: str | None,
        billing_policy_version_id: UUID | None = None,
        system_prompt_hash: str | None = None,
        runtime_snapshot: dict[str, object] | None = None,
        runtime_snapshot_hash: str | None = None,
    ) -> UUID:
        agent_run_id = uuid4()
        async with self.db.get_session() as session:
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.repository.create_agent_run",
                input={
                    "node_run_id": str(node_run_id),
                    "agent_version_id": str(agent_version_id),
                    "correlation_id": str(correlation_id),
                },
            ):
                session.add(
                    AgentRunModel(
                        agent_run_id=agent_run_id,
                        node_run_id=node_run_id,
                        agent_version_id=agent_version_id,
                        correlation_id=correlation_id,
                        input=input_payload,
                        model=model,
                        billing_policy_version_id=billing_policy_version_id,
                        system_prompt_hash=system_prompt_hash,
                        runtime_snapshot=runtime_snapshot or {},
                        runtime_snapshot_hash=runtime_snapshot_hash,
                    )
                )
            await session.commit()
        return agent_run_id

    async def update_agent_run_result(
        self,
        *,
        agent_run_id: UUID,
        status: str,
        canonical_status: str,
        output: dict | None,
        error: dict | None,
        input_tokens: int | None,
        output_tokens: int | None,
        estimated_cost: float | None,
    ) -> None:
        async with self.db.get_session() as session:
            stmt_ar = select(AgentRunModel).where(
                AgentRunModel.agent_run_id == agent_run_id
            )
            query_sql_ar = compile_query(stmt_ar)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.get_agent_run_for_result",
                input={
                    "query": query_sql_ar,
                    "params": {"agent_run_id": str(agent_run_id)},
                },
                metadata={"retriever_name": "get_agent_run_for_result"},
            ) as retriever_handle:
                result = await session.execute(stmt_ar)
                instance = result.scalar_one_or_none()

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": 1 if instance else 0,
                            "found": instance is not None,
                        }
                    )

            if instance is None:
                raise NotFoundServiceException(message="agent_run_not_found")
            instance.status = status
            instance.canonical_status = canonical_status
            instance.output = output or {}
            instance.error = error or {}
            instance.output_tokens = output_tokens
            instance.input_tokens = input_tokens
            instance.estimated_cost = estimated_cost
            instance.finished_at = sa.func.now()
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.repository.update_agent_run_result",
                input={"agent_run_id": str(agent_run_id), "status": status},
            ):
                await session.commit()

    async def acquire_flow_run_lock(
        self, flow_run_id: UUID, owner: str | None, correlation_id: UUID | None
    ) -> bool:
        async with self.db.get_session() as session:
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.repository.acquire_flow_run_lock",
                input={"flow_run_id": str(flow_run_id)},
            ):
                await session.execute(
                    select(FlowRunLockModel)
                    .where(FlowRunLockModel.flow_run_id == flow_run_id)
                    .with_for_update()
                )
                existing = await session.execute(
                    select(FlowRunLockModel).where(
                        FlowRunLockModel.flow_run_id == flow_run_id
                    )
                )
                lock = existing.scalar_one_or_none()
                if lock is None:
                    session.add(
                        FlowRunLockModel(
                            flow_run_id=flow_run_id,
                            locked_at=sa.func.now(),
                            owner=owner,
                            correlation_id=correlation_id,
                        )
                    )
                await session.commit()
        return True

    async def list_node_runs(
        self,
        *,
        tenant_id: UUID,
        flow_run_id: UUID | None = None,
        limit: int = 200,
    ) -> list[NodeRunModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(NodeRunModel)
                .join(
                    FlowRunModel,
                    NodeRunModel.flow_run_id == FlowRunModel.flow_run_id,
                )
                .join(
                    SessionModel,
                    FlowRunModel.session_id == SessionModel.session_id,
                )
                .where(SessionModel.tenant_id == tenant_id)
            )
            if flow_run_id is not None:
                stmt = stmt.where(NodeRunModel.flow_run_id == flow_run_id)
            stmt = stmt.order_by(NodeRunModel.created_at.desc()).limit(limit)
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.list_node_runs",
                input={
                    "query": query_sql,
                    "params": {
                        "tenant_id": str(tenant_id),
                        "flow_run_id": str(flow_run_id) if flow_run_id else None,
                        "limit": limit,
                    },
                },
                metadata={"retriever_name": "list_node_runs"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                runs = list(result.scalars().all())

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": len(runs),
                            "found": len(runs) > 0,
                        }
                    )

                return runs

    async def list_agent_runs(
        self,
        *,
        tenant_id: UUID,
        flow_run_id: UUID | None = None,
        limit: int = 200,
    ) -> list[AgentRunModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(AgentRunModel)
                .join(
                    NodeRunModel,
                    AgentRunModel.node_run_id == NodeRunModel.node_run_id,
                )
                .join(
                    FlowRunModel,
                    NodeRunModel.flow_run_id == FlowRunModel.flow_run_id,
                )
                .join(
                    SessionModel,
                    FlowRunModel.session_id == SessionModel.session_id,
                )
                .where(SessionModel.tenant_id == tenant_id)
            )
            if flow_run_id is not None:
                stmt = stmt.where(FlowRunModel.flow_run_id == flow_run_id)
            stmt = stmt.order_by(AgentRunModel.created_at.desc()).limit(limit)
            query_sql = compile_query(stmt)

            with self.tracer.observe(
                as_type="retriever",
                name="domain.execution.repository.list_agent_runs",
                input={
                    "query": query_sql,
                    "params": {
                        "tenant_id": str(tenant_id),
                        "flow_run_id": str(flow_run_id) if flow_run_id else None,
                        "limit": limit,
                    },
                },
                metadata={"retriever_name": "list_agent_runs"},
            ) as retriever_handle:
                result = await session.execute(stmt)
                runs = list(result.scalars().all())

                if retriever_handle:
                    retriever_handle.success(
                        output={
                            "result_count": len(runs),
                            "found": len(runs) > 0,
                        }
                    )

                return runs
