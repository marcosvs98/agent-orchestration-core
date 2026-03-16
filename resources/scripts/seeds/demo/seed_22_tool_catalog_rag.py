from __future__ import annotations

import contextlib
import sys
from pathlib import Path
from uuid import UUID, uuid4

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from adapters.cache.redis_adapter import RedisAdapter
from adapters.llm.embedding_adapter import OpenAIEmbeddingAdapter
from domain.execution.schemas.trace import TraceContext
from domain.rag.repositories.rag_repository import RagRepository
from domain.rag.schemas.rag import RagDocumentCreate
from domain.rag.services.rag_runtime_service import RagRuntimeService
from infra.database import DatabaseConnection, async_session, engine
from settings import OPENAI_API_KEY

from seeds.demo.ids import (
    RAG_CONFIG_DEMO_ID,
    TENANT_DEMO_ID,
    TOOL_CONFIG_DEMO_ID,
    TOOL_DEMO_ID,
)


class _SeedObservationHandle:
    def update(self, **kwargs) -> None:
        return None

    def success(self, *, output, metadata=None, **kwargs) -> None:
        return None

    def error(
        self,
        *,
        error_type: str,
        error_message: str,
        output=None,
        metadata=None,
        level: str = "ERROR",
        status_message: str | None = None,
        **kwargs,
    ) -> None:
        return None


class _SeedTracer:
    def start_flow_trace(
        self,
        *,
        flow_run_id: UUID,
        flow_id: UUID,
        flow_version_id: UUID,
        tenant_id: UUID,
        session_id: UUID | None,
        user_id: str | None,
        external_request_id: str | None = None,
        trace_id: UUID | None = None,
        interaction_id: UUID | None = None,
        correlation_id: UUID | None = None,
        channel: str | None = None,
        external_message_id: str | None = None,
        graph_snapshot_id: UUID | None = None,
        execution_plan_hash: str | None = None,
        flow_name: str | None = None,
    ) -> TraceContext:
        return TraceContext(
            trace_id=trace_id or uuid4(),
            flow_run_id=flow_run_id or uuid4(),
            tenant_id=tenant_id,
            session_id=session_id,
            user_id=user_id,
            root_observation_id=None,
            flow_name=flow_name,
            flow_id=flow_id,
            flow_version_id=flow_version_id,
            interaction_id=interaction_id,
            correlation_id=correlation_id,
            channel=channel,
            external_message_id=external_message_id,
            graph_snapshot_id=graph_snapshot_id,
            execution_plan_hash=execution_plan_hash,
        )

    @contextlib.contextmanager
    def flow(self, *, trace: TraceContext, input, name: str | None = None):
        handle = _SeedObservationHandle()
        yield handle

    @contextlib.contextmanager
    def observe(
        self,
        *,
        as_type: str,
        name: str,
        input,
        metadata=None,
        trace_context=None,
        **kwargs,
    ):
        handle = _SeedObservationHandle()
        yield handle

    def flush(self) -> None:
        return None

    def shutdown(self) -> None:
        return None


async def seed_tool_catalog_rag() -> None:
    if not OPENAI_API_KEY:
        raise RuntimeError("`OPENAI_API_KEY` is required for tool catalog RAG seed")

    cache_adapter = RedisAdapter()
    database_connection = DatabaseConnection(engine=engine, sessionmaker=async_session)
    rag_repository = RagRepository(database_connection)
    tracer = _SeedTracer()
    embedding_adapter = OpenAIEmbeddingAdapter(
        api_key=OPENAI_API_KEY,
        model="text-embedding-3-small",
        dimension=1536,
        tracer=tracer,
        cache_adapter=cache_adapter,
    )
    rag_runtime_service = RagRuntimeService(
        repository=rag_repository,
        embedding_adapter=embedding_adapter,
        tracer=tracer,
    )

    documents = [
        RagDocumentCreate(
            source="tool_catalog",
            doc_type="tool_catalog",
            version="createExpense.v1.cluster.direct_verbs",
            content=(
                "createExpense operation semantic aliases in Portuguese. "
                "direct verbs and typo variants for spending intent: "
                "paguei, pague, pagamos, pagamento, paguei por, paguei no, paguei na, paguei em, paguei isso, paguei hoje, "
                "pagei, paguey, pagueii, pagay, pagui, pagie, pgto, pagto, pguei, pguei x, pguei no cartao, pguei no pix, "
                "gastei, gastei com, gastei no, gastei na, gastei em, gastei isso, gasto, gastos, gastamos, gasti, gastey, gasteii, gaste, gsti, gsto, gstei, "
                "comprei, comprei um, comprei uma, comprei isso, comprei no, comprei na, comprei em, comprai, compreei, compree, compray, comprie, cmprei, cmprei x, cmprei no, cmprei na, cmprei em, "
                "desembolsei, desembolso, desembolsado, desembolsamos, desenbolsei, desembolcei, "
                "quitei, quitado, quitei isso, quitei hoje, kitei, kitey, quiteii."
            ),
            metadata={
                "category": "TOOL_CATALOG",
                "tool_id": str(TOOL_DEMO_ID),
                "tool_config_id": str(TOOL_CONFIG_DEMO_ID),
                "tool_name": "createExpense",
                "operation_id": "createExpense",
                "method": "POST",
                "path": "/createExpense",
                "cluster": "direct_verbs",
                "tool_intent": "Command",
            },
        ),
        RagDocumentCreate(
            source="tool_catalog",
            doc_type="tool_catalog",
            version="createExpense.v1.cluster.colloquial",
            content=(
                "createExpense operation semantic aliases in Portuguese. "
                "colloquial and slang spending expressions: "
                "torrei, torrei grana, torrei dinheiro, torei, torey, torray, "
                "deixei x em, deixei x no, deixei x na, larguei x em, larguei x no, larguei x na, "
                "gastei uma grana, gastei dinheiro, gastei tudo, paguei tudo, "
                "foi embora x, foi embora uma grana, foi embora dinheiro, sumiu x, sumiu uma grana."
            ),
            metadata={
                "category": "TOOL_CATALOG",
                "tool_id": str(TOOL_DEMO_ID),
                "tool_config_id": str(TOOL_CONFIG_DEMO_ID),
                "tool_name": "createExpense",
                "operation_id": "createExpense",
                "method": "POST",
                "path": "/createExpense",
                "cluster": "colloquial",
                "tool_intent": "Command",
            },
        ),
        RagDocumentCreate(
            source="tool_catalog",
            doc_type="tool_catalog",
            version="createExpense.v1.cluster.payment_methods",
            content=(
                "createExpense operation semantic aliases in Portuguese. "
                "payment method and card statements tied to expense registration: "
                "paguei no cartao, paguei no credito, paguei no debito, paguei no pix, paguei em dinheiro, paguei parcelado, "
                "parcelei, parcelei isso, parcelei em, "
                "deu no cartao, deu no pix, deu no dinheiro, "
                "foi no cartao, foi no pix, foi no debito, foi no credito, foi gasto, foi pago, foi cobrado, foi debitado, foi debitado x, "
                "saiu no cartao, saiu no pix, saiu na conta, "
                "caiu no cartao, caiu na fatura, veio na fatura, veio no cartao, veio cobranca, veio cobranca de, veio debito, veio debito de, "
                "debitou, debitou x, debitou da conta, debitou no cartao, "
                "cobrou, cobrou x, cobrou no cartao, cobrou da conta."
            ),
            metadata={
                "category": "TOOL_CATALOG",
                "tool_id": str(TOOL_DEMO_ID),
                "tool_config_id": str(TOOL_CONFIG_DEMO_ID),
                "tool_name": "createExpense",
                "operation_id": "createExpense",
                "method": "POST",
                "path": "/createExpense",
                "cluster": "payment_methods",
                "tool_intent": "Command",
            },
        ),
        RagDocumentCreate(
            source="tool_catalog",
            doc_type="tool_catalog",
            version="createExpense.v1.cluster.amount_signals",
            content=(
                "createExpense operation semantic aliases in Portuguese. "
                "amount and total signals indicating expense statements: "
                "deu, deu isso, deu tanto, deu x, deu uns, deu tipo, deu uns x, deu x reais, deu caro, deu barato, deu nisso, deu no total, "
                "foi, foi isso, foi x, foi x reais, "
                "saiu, saiu x, saiu por x, saiu isso, saiu caro, saiu barato, saiu do bolso, "
                "ficou, ficou x, ficou em x, ficou por x, ficou caro, ficou barato, "
                "me custou, custou x, custou isso, custei, custey, custeu, "
                "paguei a conta, paguei a fatura, paguei o boleto, paguei o uber, paguei o almoco, paguei a conta do, paguei a fatura do, paguei o boleto do."
            ),
            metadata={
                "category": "TOOL_CATALOG",
                "tool_id": str(TOOL_DEMO_ID),
                "tool_config_id": str(TOOL_CONFIG_DEMO_ID),
                "tool_name": "createExpense",
                "operation_id": "createExpense",
                "method": "POST",
                "path": "/createExpense",
                "cluster": "amount_signals",
                "tool_intent": "command",
            },
        ),
        RagDocumentCreate(
            source="intent_examples",
            doc_type="intent_examples",
            version="intent.query.1",
            content="consultar saldo",
            metadata={"intent_type": "query"},
        ),
        RagDocumentCreate(
            source="intent_examples",
            doc_type="intent_examples",
            version="intent.query.2",
            content="Ver despesas",
            metadata={"intent_type": "query"},
        ),
        RagDocumentCreate(
            source="intent_examples",
            doc_type="intent_examples",
            version="intent.query.3",
            content="Quanto gastei no mês",
            metadata={"intent_type": "query"},
        ),
        RagDocumentCreate(
            source="intent_examples",
            doc_type="intent_examples",
            version="intent.command.1",
            content="Registrar uma nova despesa",
            metadata={"intent_type": "command"},
        ),
        RagDocumentCreate(
            source="intent_examples",
            doc_type="intent_examples",
            version="intent.conversation.1",
            content="o que você faz",
            metadata={"intent_type": "conversation"},
        ),
        RagDocumentCreate(
            source="intent_examples",
            doc_type="intent_examples",
            version="intent.conversation.2",
            content="explique como funciona",
            metadata={"intent_type": "conversation"},
        ),
        RagDocumentCreate(
            source="intent_examples",
            doc_type="intent_examples",
            version="intent.conversation.3",
            content="quais tarefas você resolve",
            metadata={"intent_type": "conversation"},
        ),
    ]

    for document in documents:
        await rag_runtime_service.ingest_document(
            tenant_id=TENANT_DEMO_ID,
            rag_config_id=RAG_CONFIG_DEMO_ID,
            document=document,
        )
