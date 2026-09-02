import uuid
from datetime import datetime as dt

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import Column, DateTime, MetaData, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase


def uuid_pk() -> Column:
    return Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )


class ORMBaseModel(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def to_dict(self) -> dict:
        mapper = sa_inspect(self).mapper
        return {c.key: getattr(self, c.key) for c in mapper.column_attrs}

    @classmethod
    def from_dict(cls, data: dict) -> "ORMBaseModel":
        mapper = sa_inspect(cls).mapper
        filtered = {}
        for k, v in data.items():
            col = mapper.columns.get(k)
            if col is None:
                continue
            if isinstance(col.type, PG_UUID) and isinstance(v, str):
                v = uuid.UUID(v)
            elif isinstance(col.type, DateTime) and isinstance(v, str):
                v = dt.fromisoformat(v)
            filtered[k] = v
        return cls(**filtered)

    def __repr__(self):
        attrs = ", ".join(f"{k}={v!r}" for k, v in self.to_dict().items())
        return f"<{self.__class__.__name__}({attrs})>"
