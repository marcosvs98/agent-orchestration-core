from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import select

from domain.common.schemas.versioning import VersionStatus
from exceptions.service_exceptions import NotFoundServiceException
from infra.database import DatabaseConnection
from infra.database.models.flow.active_flow_version import ActiveFlowVersion as ActiveFlowVersionModel
from infra.database.models.flow.flow import Flow as FlowModel
from infra.database.models.flow.flow_version import FlowVersion as FlowVersionModel
from infra.database.models.flow.node import Node as NodeModel
from infra.database.models.flow.router import Router as RouterModel
from infra.database.models.flow.flow_graph import FlowGraph as FlowGraphModel
from infra.database.models.flow.flow_graph_draft import FlowGraphDraft as FlowGraphDraftModel
from infra.database.models.flow.flow_graph_snapshot import FlowGraphSnapshot as FlowGraphSnapshotModel
from infra.database.models.routing.routing_rule import RoutingRule as RoutingRuleModel


class FlowsRepository:
    def __init__(self, database_connection: DatabaseConnection) -> None:
        self.db = database_connection

    async def get_flow(self, flow_id: UUID) -> FlowModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(select(FlowModel).where(FlowModel.flow_id == flow_id))
            return result.scalar_one_or_none()

    async def get_flow_version(self, flow_version_id: UUID) -> FlowVersionModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(FlowVersionModel).where(FlowVersionModel.flow_version_id == flow_version_id)
            )
            return result.scalar_one_or_none()

    async def set_flow_version_status(self, *, flow_version_id: UUID, status: VersionStatus) -> None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(FlowVersionModel).where(FlowVersionModel.flow_version_id == flow_version_id)
            )
            instance = result.scalar_one_or_none()
            if instance is None:
                raise NotFoundServiceException(message="flow_version_not_found")
            instance.status = str(status)
            await session.commit()

    async def list_nodes_for_flow_version(self, flow_version_id: UUID) -> list[NodeModel]:
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

    async def get_flow_graph_by_flow_version(self, flow_version_id: UUID) -> FlowGraphModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(FlowGraphModel).where(FlowGraphModel.flow_version_id == flow_version_id)
            )
            return result.scalar_one_or_none()

    async def create_flow_graph(
        self, *, flow_version_id: UUID, definition: dict, created_by: str
    ) -> FlowGraphModel:
        async with self.db.get_session() as session:
            existing = await session.execute(
                select(FlowGraphModel).where(FlowGraphModel.flow_version_id == flow_version_id)
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
                select(ActiveFlowVersionModel).where(ActiveFlowVersionModel.flow_id == flow_id)
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
                select(ActiveFlowVersionModel).where(ActiveFlowVersionModel.flow_id == flow_id)
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

    async def get_flow_graph_draft(self, flow_version_id: UUID) -> FlowGraphDraftModel | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(FlowGraphDraftModel).where(FlowGraphDraftModel.flow_version_id == flow_version_id)
            )
            return result.scalar_one_or_none()

    async def upsert_flow_graph_draft(
        self, *, flow_version_id: UUID, definition: dict, principal_id: str
    ) -> FlowGraphDraftModel:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(FlowGraphDraftModel).where(FlowGraphDraftModel.flow_version_id == flow_version_id)
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
            existing.status = "DRAFT"
            existing.validated_at = None
            existing.validated_by = None
            await session.commit()
            return existing

    async def validate_flow_graph_draft(
        self, *, flow_version_id: UUID, principal_id: str
    ) -> FlowGraphDraftModel:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(FlowGraphDraftModel).where(FlowGraphDraftModel.flow_version_id == flow_version_id)
            )
            instance = result.scalar_one_or_none()
            if instance is None:
                raise NotFoundServiceException(message="flow_graph_draft_not_found")
            instance.status = "VALIDATED"
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
                select(FlowGraphSnapshotModel).where(FlowGraphSnapshotModel.flow_version_id == flow_version_id)
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
