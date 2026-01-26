from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import select

from domain.common.schemas.versioning import VersionStatus
from exceptions.service_exceptions import (
    DomainValidationException,
    NotFoundServiceException,
)
from infra.database import DatabaseConnection
from infra.database.models.flow.active_flow_version import (
    ActiveFlowVersion as ActiveFlowVersionModel,
)
from infra.database.models.flow.flow import Flow as FlowModel
from infra.database.models.flow.flow_version import FlowVersion as FlowVersionModel
from infra.database.models.flow.node import Node as NodeModel
from infra.database.models.flow.router import Router as RouterModel
from infra.database.models.flow.flow_graph import FlowGraph as FlowGraphModel
from infra.database.models.flow.flow_graph_draft import (
    FlowGraphDraft as FlowGraphDraftModel,
)
from infra.database.models.flow.flow_graph_snapshot import (
    FlowGraphSnapshot as FlowGraphSnapshotModel,
)
from infra.database.models.routing.routing_rule import RoutingRule as RoutingRuleModel
from infra.database.models.routing.condition_expression import (
    ConditionExpression as ConditionExpressionModel,
)


class FlowsRepository:
    def __init__(self, database_connection: DatabaseConnection) -> None:
        self.db = database_connection

    async def get_flow(self, flow_id: UUID) -> FlowModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(FlowModel).where(FlowModel.flow_id == flow_id)
            )
            return result.scalar_one_or_none()

    async def get_flow_version(self, flow_version_id: UUID) -> FlowVersionModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(FlowVersionModel).where(
                    FlowVersionModel.flow_version_id == flow_version_id
                )
            )
            return result.scalar_one_or_none()

    async def set_flow_version_status(
        self, *, flow_version_id: UUID, status: VersionStatus
    ) -> None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(FlowVersionModel).where(
                    FlowVersionModel.flow_version_id == flow_version_id
                )
            )
            instance = result.scalar_one_or_none()
            if instance is None:
                raise NotFoundServiceException(message="flow_version_not_found")
            instance.status = str(status)
            await session.commit()

    async def get_node(self, node_id: UUID) -> NodeModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(NodeModel).where(NodeModel.node_id == node_id)
            )
            return result.scalar_one_or_none()

    async def list_nodes_for_flow_version(
        self, flow_version_id: UUID
    ) -> list[NodeModel]:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(NodeModel).where(NodeModel.flow_version_id == flow_version_id)
            )
            return list(result.scalars().all())

    async def list_routing_rules_for_flow_version(
        self, flow_version_id: UUID
    ) -> list[RoutingRuleModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(RoutingRuleModel)
                .join(RouterModel, RoutingRuleModel.router_id == RouterModel.router_id)
                .join(NodeModel, RouterModel.node_id == NodeModel.node_id)
                .where(NodeModel.flow_version_id == flow_version_id)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_flow_graph_by_flow_version(
        self, flow_version_id: UUID
    ) -> FlowGraphModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(FlowGraphModel).where(
                    FlowGraphModel.flow_version_id == flow_version_id
                )
            )
            return result.scalar_one_or_none()

    async def create_flow_graph(
        self, *, flow_version_id: UUID, definition: dict, created_by: str
    ) -> FlowGraphModel:
        async with self.db.get_session() as session:
            existing = await session.execute(
                select(FlowGraphModel).where(
                    FlowGraphModel.flow_version_id == flow_version_id
                )
            )
            if existing.scalar_one_or_none():
                raise NotFoundServiceException(message="flow_graph_exists")
            instance = FlowGraphModel(
                flow_version_id=flow_version_id,
                definition=definition,
                created_by=created_by,
            )
            session.add(instance)
            await session.commit()
            return instance

    async def get_active_flow_version_id(self, flow_id: UUID) -> UUID | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(ActiveFlowVersionModel).where(
                    ActiveFlowVersionModel.flow_id == flow_id
                )
            )
            row = result.scalar_one_or_none()
            return row.flow_version_id if row else None

    async def upsert_active_flow_version(
        self,
        *,
        flow_id: UUID,
        flow_version_id: UUID,
        activated_by_principal_id: str,
        justification: str,
        flow_graph_snapshot_id: UUID | None = None,
    ) -> None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(ActiveFlowVersionModel).where(
                    ActiveFlowVersionModel.flow_id == flow_id
                )
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                session.add(
                    ActiveFlowVersionModel(
                        flow_id=flow_id,
                        flow_version_id=flow_version_id,
                        activated_by_principal_id=activated_by_principal_id,
                        justification=justification,
                        flow_graph_snapshot_id=flow_graph_snapshot_id,
                    )
                )
            else:
                existing.flow_version_id = flow_version_id
                existing.activated_by_principal_id = activated_by_principal_id
                existing.justification = justification
                existing.flow_graph_snapshot_id = flow_graph_snapshot_id
            await session.commit()

    async def get_flow_graph_draft(
        self, flow_version_id: UUID
    ) -> FlowGraphDraftModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(FlowGraphDraftModel).where(
                    FlowGraphDraftModel.flow_version_id == flow_version_id
                )
            )
            return result.scalar_one_or_none()

    async def upsert_flow_graph_draft(
        self, *, flow_version_id: UUID, definition: dict, principal_id: str
    ) -> FlowGraphDraftModel:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(FlowGraphDraftModel).where(
                    FlowGraphDraftModel.flow_version_id == flow_version_id
                )
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                instance = FlowGraphDraftModel(
                    flow_version_id=flow_version_id,
                    definition=definition,
                    created_by=principal_id,
                )
                session.add(instance)
                await session.commit()
                return instance
            existing.definition = definition
            existing.status = "DRAFT"  # TODO: hardcoded value - Use StrEnum P0
            existing.validated_at = None
            existing.validated_by = None
            await session.commit()
            return existing

    async def validate_flow_graph_draft(
        self, *, flow_version_id: UUID, principal_id: str
    ) -> FlowGraphDraftModel:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(FlowGraphDraftModel).where(
                    FlowGraphDraftModel.flow_version_id == flow_version_id
                )
            )
            instance = result.scalar_one_or_none()
            if instance is None:
                raise NotFoundServiceException(message="flow_graph_draft_not_found")
            instance.status = "VALIDATED"  # TODO: hardcoded value - Use StrEnum P0
            instance.validated_by = principal_id
            instance.validated_at = sa.func.now()  # type: ignore[attr-defined]
            await session.commit()
            return instance

    async def create_flow_graph_snapshot(
        self,
        *,
        flow_version_id: UUID,
        snapshot: dict,
        graph_hash: str,
        compiled_by: str,
    ) -> FlowGraphSnapshotModel:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(FlowGraphSnapshotModel).where(
                    FlowGraphSnapshotModel.flow_version_id == flow_version_id
                )
            )
            if result.scalar_one_or_none():
                raise NotFoundServiceException(message="flow_graph_snapshot_exists")
            instance = FlowGraphSnapshotModel(
                flow_version_id=flow_version_id,
                snapshot=snapshot,
                graph_hash=graph_hash,
                compiled_by=compiled_by,
            )
            session.add(instance)
            await session.commit()
            return instance

    async def get_flow_graph_snapshot_by_flow_version(
        self, flow_version_id: UUID
    ) -> FlowGraphSnapshotModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(FlowGraphSnapshotModel).where(
                    FlowGraphSnapshotModel.flow_version_id == flow_version_id
                )
            )
            return result.scalar_one_or_none()

    async def list_flows(self, *, tenant_id: UUID, limit: int = 200) -> list[FlowModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(FlowModel)
                .where(FlowModel.tenant_id == tenant_id)
                .order_by(FlowModel.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def create_flow(
        self,
        *,
        tenant_id: UUID,
        name: str | None,
        description: str | None = None,
        tags: list[str] | None = None,
        created_by: str,
    ) -> FlowModel:
        async with self.db.get_session() as session:
            instance = FlowModel(
                tenant_id=tenant_id,
                name=name,
                description=description,
                tags=tags,
                created_by=created_by,
            )
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance

    async def list_flow_versions(
        self, *, flow_id: UUID, status_filter: list[str] | None = None
    ) -> list[FlowVersionModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(FlowVersionModel)
                .where(FlowVersionModel.flow_id == flow_id)
                .order_by(
                    FlowVersionModel.version_major.desc(),
                    FlowVersionModel.version_minor.desc(),
                    FlowVersionModel.version_patch.desc(),
                )
            )
            if status_filter:
                stmt = stmt.where(FlowVersionModel.status.in_(status_filter))
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def create_flow_version(
        self,
        *,
        flow_id: UUID,
        source_version_id: UUID | None = None,
        version_major: int | None = None,
        version_minor: int | None = None,
        version_patch: int | None = None,
        min_agent_version_major: int | None = None,
        min_agent_version_minor: int | None = None,
        min_agent_version_patch: int | None = None,
        created_by: str,
    ) -> FlowVersionModel:
        async with self.db.get_session() as session:
            if source_version_id is not None:
                source_version = await session.execute(
                    select(FlowVersionModel).where(
                        FlowVersionModel.flow_version_id == source_version_id
                    )
                )
                source = source_version.scalar_one_or_none()
                if source is None:
                    raise NotFoundServiceException(message="source_version_not_found")
                if version_major is None:
                    version_major = source.version_major
                if version_minor is None:
                    version_minor = source.version_minor
                if version_patch is None:
                    version_patch = source.version_patch + 1
                if min_agent_version_major is None:
                    min_agent_version_major = source.min_agent_version_major
                if min_agent_version_minor is None:
                    min_agent_version_minor = source.min_agent_version_minor
                if min_agent_version_patch is None:
                    min_agent_version_patch = source.min_agent_version_patch

            if version_major is None or version_minor is None or version_patch is None:
                last_version = await session.execute(
                    select(FlowVersionModel)
                    .where(FlowVersionModel.flow_id == flow_id)
                    .order_by(
                        FlowVersionModel.version_major.desc(),
                        FlowVersionModel.version_minor.desc(),
                        FlowVersionModel.version_patch.desc(),
                    )
                    .limit(1)
                )
                last = last_version.scalar_one_or_none()
                if last is None:
                    version_major = 1
                    version_minor = 0
                    version_patch = 0
                else:
                    if version_major is None:
                        version_major = last.version_major
                    if version_minor is None:
                        version_minor = last.version_minor
                    if version_patch is None:
                        version_patch = last.version_patch + 1

            instance = FlowVersionModel(
                flow_id=flow_id,
                status="DRAFT",  # TODO: hardcoded value - Use StrEnum P0
                version_major=version_major,
                version_minor=version_minor,
                version_patch=version_patch,
                min_agent_version_major=min_agent_version_major,
                min_agent_version_minor=min_agent_version_minor,
                min_agent_version_patch=min_agent_version_patch,
            )
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance

    async def create_node(
        self, *, flow_version_id: UUID, ai_task_id: UUID | None, created_by: str
    ) -> NodeModel:
        async with self.db.get_session() as session:
            version = await session.execute(
                select(FlowVersionModel).where(
                    FlowVersionModel.flow_version_id == flow_version_id
                )
            )
            if version.scalar_one_or_none() is None:
                raise NotFoundServiceException(message="flow_version_not_found")
            instance = NodeModel(flow_version_id=flow_version_id, ai_task_id=ai_task_id)
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance

    async def list_routers(
        self, *, tenant_id: UUID, limit: int = 200
    ) -> list[RouterModel]:
        async with self.db.get_session() as session:
            stmt = (
                select(RouterModel)
                .join(NodeModel, RouterModel.node_id == NodeModel.node_id)
                .join(
                    FlowVersionModel,
                    NodeModel.flow_version_id == FlowVersionModel.flow_version_id,
                )
                .join(FlowModel, FlowVersionModel.flow_id == FlowModel.flow_id)
                .where(FlowModel.tenant_id == tenant_id)
                .order_by(RouterModel.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_router(self, router_id: UUID) -> RouterModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(RouterModel).where(RouterModel.router_id == router_id)
            )
            return result.scalar_one_or_none()

    async def create_router(self, *, node_id: UUID, created_by: str) -> RouterModel:
        async with self.db.get_session() as session:
            node = await session.execute(
                select(NodeModel).where(NodeModel.node_id == node_id)
            )
            if node.scalar_one_or_none() is None:
                raise NotFoundServiceException(message="node_not_found")
            instance = RouterModel(node_id=node_id)
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance

    async def create_condition_expression(
        self, *, expression: str | None, created_by: str
    ) -> ConditionExpressionModel:
        async with self.db.get_session() as session:
            instance = ConditionExpressionModel(expression=expression)
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance

    async def create_routing_rule(
        self,
        *,
        router_id: UUID,
        condition_expression_id: UUID,
        from_node_id: UUID,
        to_node_id: UUID,
        created_by: str,
    ) -> RoutingRuleModel:
        async with self.db.get_session() as session:
            router = await session.execute(
                select(RouterModel).where(RouterModel.router_id == router_id)
            )
            router_instance = router.scalar_one_or_none()
            if router_instance is None:
                raise NotFoundServiceException(message="router_not_found")

            condition = await session.execute(
                select(ConditionExpressionModel).where(
                    ConditionExpressionModel.condition_expression_id
                    == condition_expression_id
                )
            )
            if condition.scalar_one_or_none() is None:
                raise NotFoundServiceException(message="condition_expression_not_found")

            from_node = await session.execute(
                select(NodeModel).where(NodeModel.node_id == from_node_id)
            )
            from_node_instance = from_node.scalar_one_or_none()
            if from_node_instance is None:
                raise NotFoundServiceException(message="from_node_not_found")

            to_node = await session.execute(
                select(NodeModel).where(NodeModel.node_id == to_node_id)
            )
            to_node_instance = to_node.scalar_one_or_none()
            if to_node_instance is None:
                raise NotFoundServiceException(message="to_node_not_found")

            router_node = await session.execute(
                select(NodeModel).where(NodeModel.node_id == router_instance.node_id)
            )
            router_node_instance = router_node.scalar_one_or_none()
            if router_node_instance is None:
                raise NotFoundServiceException(message="router_node_not_found")

            if (
                from_node_instance.flow_version_id != to_node_instance.flow_version_id
                or from_node_instance.flow_version_id
                != router_node_instance.flow_version_id
            ):
                raise DomainValidationException(
                    message="nodes_must_belong_to_same_flow_version"
                )

            instance = RoutingRuleModel(
                router_id=router_id,
                condition_expression_id=condition_expression_id,
                from_node_id=from_node_id,
                to_node_id=to_node_id,
            )
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance
