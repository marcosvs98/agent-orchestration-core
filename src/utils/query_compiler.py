from typing import Any
from settings import TRACING_ENABLED

from sqlalchemy.dialects import postgresql


def compile_query(stmt: Any) -> str | None:
    query_str: str | None = None
    if TRACING_ENABLED:
        try:
            if hasattr(stmt, "compile"):
                compiled = stmt.compile(dialect=postgresql.dialect())
                query_str = str(compiled)
            elif isinstance(stmt, str):
                query_str = stmt
            else:
                query_str = str(stmt)
        except Exception:
            pass
    return query_str
