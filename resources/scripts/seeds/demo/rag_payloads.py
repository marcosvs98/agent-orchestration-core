from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

for _ROOT in Path(__file__).resolve().parents:
    if (_ROOT / "pyproject.toml").exists():
        sys.path.insert(0, str(_ROOT / "src"))
        sys.path.insert(0, str(_ROOT / "resources" / "scripts"))
        sys.path.insert(0, str(_ROOT))
        break
else:
    raise RuntimeError("repository root not found")

from domain.execution.services.graph_runtime.types import ToolIntentFilter
from domain.governance.schemas.memory_policy import MemoryPolicySource
from domain.rag.schemas.rag import RagDocumentCreate

_DEMO_SEMANTIC_ALIASES: dict[str, str] = {
    "create_expense": (
        "registar despesa, registrar gasto, lancar despesa, anotar um gasto, adicionar despesa, "
        "criar despesa, guardar um gasto, gastei, paguei, comprei, gastei 100 reais, "
        "paguei no mercado, despesa em dinheiro, registar compra, quero registar um gasto"
    ),
    "list_expenses": (
        "listar despesas, ver meus gastos, mostrar despesas, consultar gastos, "
        "quais foram as minhas despesas, historico de gastos, ver lancamentos"
    ),
    "get_expense_summary": (
        "resumo de gastos, total por categoria, quanto gastei no total, "
        "sumario de despesas, gastos agrupados por categoria, relatorio de gastos"
    ),
}

_DEMO_TARGET_UTTERANCE = (
    "Gastei 100 reais em comida ontem no mercado, utilizando a conta PF do Santander "
    "com metodo de pagamento PIX"
)


def _derive_tool_intent_from_method(method: str | None) -> str:
    upper = (method or "GET").upper()
    if upper == "GET":
        return ToolIntentFilter.QUERY.value
    if upper in {"POST", "PUT", "PATCH", "DELETE"}:
        return ToolIntentFilter.COMMAND.value
    return ToolIntentFilter.QUERY.value


def _tool_catalog_meta(row: dict[str, Any]) -> dict[str, Any]:
    oid = str(row["operation_id"])
    return {
        "category": "TOOL_CATALOG",
        "tool_id": str(row["tool_id"]),
        "tool_config_id": str(row["tool_config_id"]),
        "tool_name": str(row["tool_name"]),
        "operation_id": oid,
        "method": str(row["method"]),
        "path": str(row["path"]),
        "tool_intent": _derive_tool_intent_from_method(str(row.get("method") or "")),
    }


def _semantic_alias_text(row: dict[str, Any]) -> str:
    oid = str(row["operation_id"])
    if oid in _DEMO_SEMANTIC_ALIASES:
        return _DEMO_SEMANTIC_ALIASES[oid]
    tool_name = str(row["tool_name"])
    path = str(row["path"])
    method = str(row.get("method") or "GET").upper()
    if method == "GET":
        bits = [f"{tool_name} consulta GET", f"caminho {path}", "ver, listar, mostrar, consultar"]
    else:
        bits = [
            f"{tool_name} operacao HTTP {method}",
            f"caminho {path}",
            "registar, criar, adicionar, lancar, anotar",
        ]
    summary = row.get("summary")
    if summary:
        bits.append(str(summary))
    return ". ".join(bits)


def _create_expense_cluster_docs(row: dict[str, Any]) -> list[RagDocumentCreate]:
    meta = _tool_catalog_meta(row)
    oid = str(row["operation_id"])
    return [
        RagDocumentCreate(
            source="tool_catalog",
            doc_type="tool_catalog",
            version=f"{oid}.v1.body",
            content=(
                "Campos aceites ao registar uma despesa: amount (valor gasto, numero), "
                "description (descricao curta do gasto), currency (moeda ISO como BRL, EUR, USD), "
                "category (categoria: comida, transporte, saude, lazer), "
                "occurred_on (data no formato YYYY-MM-DD; 'ontem' e o dia anterior), "
                "payment_method (PIX, cartao, dinheiro, transferencia), "
                "account_label (nome da conta, por exemplo 'conta PF do Santander'). "
                "Apenas amount e description sao obrigatorios. Nunca inventar valores."
            ),
            metadata={**meta, "cluster": "request_body"},
        ),
        RagDocumentCreate(
            source="tool_catalog",
            doc_type="tool_catalog",
            version=f"{oid}.v1.ex",
            content=(
                f"Exemplos de pedidos que registam uma despesa: '{_DEMO_TARGET_UTTERANCE}'. "
                "'Paguei 35 no almoco, regista por favor'. "
                "'Anota um gasto de 200 em transporte'. "
                "'Lanca uma despesa de 50 euros na farmacia'. "
                "'Gastei 80 reais no supermercado com cartao'."
            ),
            metadata={**meta, "cluster": "examples"},
        ),
        RagDocumentCreate(
            source="tool_catalog",
            doc_type="tool_catalog",
            version=f"{oid}.v1.dis",
            content=(
                "Desambiguacao entre registar e consultar despesas. "
                "Verbos de accao (gastei, paguei, comprei, registar, criar, lancar, anotar, "
                "adicionar) indicam create_expense, que e POST /expenses. "
                "Verbos de consulta (ver, listar, mostrar, consultar, quanto gastei no total) "
                "indicam list_expenses ou get_expense_summary, que sao GET."
            ),
            metadata={**meta, "cluster": "disambiguation"},
        ),
    ]


def demo_knowledge_base_documents() -> list[RagDocumentCreate]:
    return [
        RagDocumentCreate(
            source="demo_kb",
            doc_type="knowledge",
            version="demo.kb.v1.about",
            content=(
                "Este assistente de demonstracao regista e consulta despesas pessoais. "
                "Pode guardar um gasto novo, listar os gastos anteriores e resumir os totais "
                "por categoria ou por metodo de pagamento."
            ),
            metadata={"category": "GENERAL"},
        ),
        RagDocumentCreate(
            source="demo_kb",
            doc_type="knowledge",
            version="demo.kb.v1.currency",
            content=(
                "Os valores sao guardados na moeda indicada pelo utilizador. "
                "Quando a moeda nao e indicada, o sistema assume BRL. "
                "As datas usam o formato YYYY-MM-DD."
            ),
            metadata={"category": "GENERAL"},
        ),
        RagDocumentCreate(
            source="demo_kb",
            doc_type="knowledge",
            version="demo.kb.v1.categories",
            content=(
                "As categorias de despesa mais comuns sao comida, transporte, saude, "
                "habitacao, lazer e educacao. Um gasto sem categoria fica como uncategorised."
            ),
            metadata={"category": "GENERAL"},
        ),
    ]


def demo_tool_catalog_seed_documents(
    *,
    tool_id: UUID,
    tool_config_id: UUID,
) -> list[RagDocumentCreate]:
    return demo_tool_catalog_documents(
        [
            {
                "tool_id": tool_id,
                "tool_config_id": tool_config_id,
                "tool_name": "create_expense",
                "operation_id": "create_expense",
                "method": "POST",
                "path": "/expenses",
                "summary": "Record a new expense entry.",
                "description": None,
            }
        ]
    )


def demo_tool_catalog_documents(
    rows: list[dict[str, Any]],
) -> list[RagDocumentCreate]:
    docs: list[RagDocumentCreate] = []
    for row in rows:
        oid = str(row["operation_id"])
        tool_name = str(row["tool_name"])
        meta = _tool_catalog_meta(row)
        docs.append(
            RagDocumentCreate(
                source="tool_catalog",
                doc_type="tool_catalog",
                version=f"{oid}.v1.sa",
                content=(
                    f"Formas de pedir a operacao {tool_name}. {_semantic_alias_text(row)}"
                ),
                metadata={**meta, "cluster": "semantic_aliases"},
            ),
        )
        parts: list[str] = [tool_name]
        summary = row.get("summary")
        if summary:
            parts.append(str(summary))
        description = row.get("description")
        if description:
            parts.append(str(description))
        docs.append(
            RagDocumentCreate(
                source="tool_catalog",
                doc_type="tool_catalog",
                version=f"{oid}.v1.su",
                content=". ".join(parts),
                metadata={**meta, "cluster": "api_summary"},
            ),
        )
        if oid == "create_expense":
            docs.extend(_create_expense_cluster_docs(row))
    return docs


def demo_user_memory_write_item_dict(
    *,
    user_id: str,
    rag_config_id: UUID,
    utterance: str,
    topic: str,
    schema_id: str = "user.profile_signal.v1",
    schema_version: int = 1,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    if observed_at is None:
        observed_at = datetime.now(timezone.utc)
    return {
        "schema_id": schema_id,
        "schema_version": schema_version,
        "data": {
            "natural_language": utterance,
            "topic": topic,
            "subject_user_id": user_id,
        },
        "source": MemoryPolicySource.EXPLICIT_USER.value,
        "rag_config_id": rag_config_id,
        "observed_at": observed_at,
    }


def demo_tenant_knowledge_probe_document(*, run_ref: str) -> RagDocumentCreate:
    tenant_query = (
        "The demo assistant records and looks up personal expenses; "
        "it organizes income, expenses, balances and financial goals."
    )
    return RagDocumentCreate(
        source="validate_rag_runtime_scenarios",
        doc_type="tenant_knowledge_probe",
        content=f"{tenant_query}\nrun_ref={run_ref}",
        version="1.0",
        metadata={"run_ref": run_ref},
    )


def demo_intent_examples_probe_document(*, user_input: str, run_ref: str) -> RagDocumentCreate:
    return RagDocumentCreate(
        source="intent_examples",
        doc_type="intent_examples",
        content=f"{user_input}\nrun_ref={run_ref}",
        version="1.0",
        metadata={"intent_type": "query"},
    )


def demo_tool_catalog_probe_document(
    *,
    user_input: str,
    tool_id: UUID,
    tool_config_id: UUID,
    run_ref: str,
) -> RagDocumentCreate:
    return RagDocumentCreate(
        source="tool_catalog",
        doc_type="tool_catalog",
        content=f"{user_input}\nrun_ref={run_ref}",
        version="1.0",
        metadata={
            "category": "TOOL_CATALOG",
            "tool_id": str(tool_id),
            "tool_config_id": str(tool_config_id),
            "tool_name": "create_expense",
            "operation_id": "create_expense",
            "method": "GET",
            "path": "/api/v1/spending/by-category",
            "tool_intent": ToolIntentFilter.QUERY.value,
            "run_ref": run_ref,
        },
    )


def demo_long_chunking_sample_text(*, run_tag: str) -> str:
    return (
        "Section A. "
        + ("Lorem ipsum dolor sit amet. " * 400)
        + f"\nrun_tag={run_tag}\n"
        + ("Consectetur adipiscing elit. " * 400)
    )
