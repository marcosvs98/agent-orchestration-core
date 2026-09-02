from sqlalchemy import Index

from infra.database.models.flow.flow_deployment import FlowDeployment


def _indexes() -> dict[str, Index]:
    return {arg.name: arg for arg in FlowDeployment.__table_args__ if isinstance(arg, Index)}


def test_active_deployment_slot_is_a_partial_unique_index():
    index = _indexes()["uq_flow_deployment_active_slot"]

    assert index.unique is True
    assert [column.name for column in index.columns] == ["flow_id", "environment"]


def test_active_slot_index_only_applies_to_active_rows():
    index = _indexes()["uq_flow_deployment_active_slot"]

    where_clause = str(index.dialect_options["postgresql"]["where"])

    assert "ACTIVE" in where_clause


def test_status_is_not_part_of_the_uniqueness_key():
    index = _indexes()["uq_flow_deployment_active_slot"]

    assert "status" not in [column.name for column in index.columns]


def test_no_full_table_unique_constraint_on_status_remains():
    from sqlalchemy import UniqueConstraint

    constraints = [
        arg for arg in FlowDeployment.__table_args__ if isinstance(arg, UniqueConstraint)
    ]

    assert constraints == []
