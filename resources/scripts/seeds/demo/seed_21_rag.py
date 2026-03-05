from __future__ import annotations

import contextlib
import sys
from pathlib import Path
from uuid import UUID, uuid4

project_root = Path(__file__).resolve().parents[3]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from sqlalchemy import select

from adapters.cache.redis_adapter import RedisAdapter
from adapters.llm.embedding_adapter import OpenAIEmbeddingAdapter
from domain.common.schemas.versioning import VersionStatus
from domain.execution.schemas.trace import TraceContext
from domain.rag.repositories.rag_repository import RagRepository
from domain.rag.schemas.rag import RagConfigOptions, RagDocumentCreate
from domain.rag.services.rag_runtime_service import RagRuntimeService
from infra.database import get_db
from infra.database import DatabaseConnection, async_session, engine
from infra.database.models.rag.rag_config import RagConfig
from infra.database.models.rag.vector_store import VectorStore
from settings import OPENAI_API_KEY

from seeds.demo.ids import (
    RAG_CONFIG_DEMO_ID,
    TENANT_DEMO_ID,
    VECTOR_STORE_DEMO_ID,
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


async def seed_rag() -> None:
    async with get_db() as session:
        result = await session.execute(
            select(VectorStore).where(
                VectorStore.vector_store_id == VECTOR_STORE_DEMO_ID
            )
        )
        existing_store = result.scalar_one_or_none()

        if existing_store is None:
            vector_store = VectorStore(
                vector_store_id=VECTOR_STORE_DEMO_ID,
                name="Assistente de Bolso - Conhecimento",
            )
            session.add(vector_store)
            await session.commit()

        result = await session.execute(
            select(RagConfig).where(RagConfig.rag_config_id == RAG_CONFIG_DEMO_ID)
        )
        existing_config = result.scalar_one_or_none()

        if existing_config is None:
            options = RagConfigOptions().model_dump(mode="json")
            rag_config = RagConfig(
                rag_config_id=RAG_CONFIG_DEMO_ID,
                tenant_id=TENANT_DEMO_ID,
                vector_store_id=VECTOR_STORE_DEMO_ID,
                status=VersionStatus.PUBLISHED.value,
                version_major=1,
                version_minor=0,
                version_patch=0,
                options=options,
            )
            session.add(rag_config)
            await session.commit()
        else:
            options = existing_config.options
            if not options:
                options = RagConfigOptions().model_dump(mode="json")
                existing_config.options = options
            if existing_config.status != VersionStatus.PUBLISHED.value:
                existing_config.status = VersionStatus.PUBLISHED.value
            await session.commit()

    if not OPENAI_API_KEY:
        raise RuntimeError("`OPENAI_API_KEY` is required for RAG seed ingestion")

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
            source="assistente-bolso",
            doc_type="identity_proposito",
            content=(
                "Identidade: O Assistente de Bolso é uma IA de controle financeiro pessoal operada via WhatsApp. "
                "Atua como interface conversacional para organização de receitas, despesas, saldos, metas financeiras e compromissos. "
                "É um operador financeiro conversacional. Não substitui contador, assessor de investimentos ou consultor jurídico/tributário. "
                "Seu papel é fornecer organização, visibilidade e apoio operacional. "
                "Proposta de valor: Conecta automaticamente às contas bancárias via Open Finance; categoriza ganhos e gastos; "
                "permite consultas financeiras por mensagem; gera relatórios e resumos periódicos; gerencia compromissos e lembretes; "
                "pode integrar com Google Agenda; opera de forma simples, direto no WhatsApp. A experiência deve ser conversacional, prática e sem fricção. "
                "Propósito: Organizar a vida financeira do usuário; reduzir fricção no registro de movimentações; "
                "fornecer clareza sobre para onde o dinheiro está indo; apoiar criação e acompanhamento de metas financeiras; "
                "centralizar finanças e compromissos em uma única conversa. "
                "Tom de voz: profissional, claro, direto, objetivo, didático quando necessário, respeitoso. "
                "Small talk é permitido, mas deve ser breve e reconduzido para utilidade prática."
            ),
            version="1",
            metadata={"topic": "identity_proposito"},
        ),
        RagDocumentCreate(
            source="assistente-bolso",
            doc_type="escopo",
            content=(
                "Escopo funcional – Inclui: Registro manual de despesas e receitas via linguagem natural; "
                "registro automático via conexão bancária; consulta de saldo; consulta de gastos por categoria; "
                "consulta de economia acumulada; relatórios mensais e resumos periódicos; criação de metas financeiras; "
                "cálculo simples de quanto precisa economizar para atingir uma meta; criação e consulta de compromissos; "
                "criação de lembretes; integração com Google Agenda. "
                "Não inclui: Aconselhamento de investimentos avançado; planejamento tributário; "
                "decisões financeiras autônomas; simulação de operações financeiras inexistentes."
            ),
            version="1",
            metadata={"topic": "scope"},
        ),
        RagDocumentCreate(
            source="assistente-bolso",
            doc_type="faq_conexao_bancaria",
            content=(
                "FAQ – Conexão Bancária. "
                "Pergunta: Como conecto minha conta bancária? "
                "Resposta: Você pode conectar sua conta por meio do fluxo de Open Finance. Após autorização, suas movimentações passam a ser sincronizadas automaticamente. "
                "Pergunta: Preciso atualizar manualmente as transações? "
                "Resposta: Não. Após a conexão, as movimentações são sincronizadas automaticamente. "
                "Pergunta: Minhas transações são registradas automaticamente? "
                "Resposta: Sim, quando a conta está conectada, receitas e despesas são importadas e categorizadas automaticamente."
            ),
            version="1",
            metadata={"topic": "faq", "section": "conexao_bancaria"},
        ),
        RagDocumentCreate(
            source="assistente-bolso",
            doc_type="faq_registro_despesas_receitas",
            content=(
                "FAQ – Registro de Despesas e Receitas. "
                "Pergunta: Como registro uma despesa? "
                "Resposta: Basta informar o valor e a descrição, por exemplo: “Gastei 120 reais no mercado”. Se houver integração ativa, o sistema pode já ter registrado automaticamente. "
                "Pergunta: Como registro uma receita? "
                "Resposta: Informe o valor e a origem, por exemplo: “Recebi 2.000 reais de salário”. "
                "Pergunta: Preciso informar a data? "
                "Resposta: Se não informar, será considerada a data atual."
            ),
            version="1",
            metadata={"topic": "faq", "section": "registro"},
        ),
        RagDocumentCreate(
            source="assistente-bolso",
            doc_type="faq_consultas_financeiras",
            content=(
                "FAQ – Consultas Financeiras. "
                "Pergunta: Quanto eu economizei este mês? "
                "Resposta: O assistente calcula com base nas receitas e despesas registradas no período. "
                "Pergunta: Quais são meus maiores gastos? "
                "Resposta: O assistente pode informar os principais gastos por categoria no período solicitado. "
                "Pergunta: Qual meu saldo atual? "
                "Resposta: O saldo é calculado com base nas contas conectadas e movimentações registradas."
            ),
            version="1",
            metadata={"topic": "faq", "section": "consultas"},
        ),
        RagDocumentCreate(
            source="assistente-bolso",
            doc_type="faq_relatorios",
            content=(
                "FAQ – Relatórios e Resumos. "
                "Pergunta: Recebo relatório mensal? "
                "Resposta: Sim, o assistente pode fornecer resumos mensais com visão consolidada de receitas, despesas e economia. "
                "Pergunta: Posso ver meus gastos por categoria? "
                "Resposta: Sim, é possível consultar gastos segmentados por categoria."
            ),
            version="1",
            metadata={"topic": "faq", "section": "relatorios"},
        ),
        RagDocumentCreate(
            source="assistente-bolso",
            doc_type="faq_metas_financeiras",
            content=(
                "FAQ – Metas Financeiras. "
                "Pergunta: Posso criar uma meta financeira? "
                "Resposta: Sim. Você pode definir um objetivo, como “Quero economizar 5.000 reais”. O assistente ajuda a calcular quanto precisa poupar por período. "
                "Pergunta: Como sei quanto posso gastar por dia para atingir minha meta? "
                "Resposta: O assistente pode calcular um limite médio de gasto com base no prazo e no valor da meta."
            ),
            version="1",
            metadata={"topic": "faq", "section": "metas"},
        ),
        RagDocumentCreate(
            source="assistente-bolso",
            doc_type="faq_uso_geral",
            content=(
                "FAQ – Uso Geral. "
                "Pergunta: Como começo a usar? "
                "Resposta: Inicie a conversa com uma saudação e siga o fluxo de configuração, incluindo conexão bancária se desejar sincronização automática. "
                "Pergunta: Posso usar apenas por mensagem? "
                "Resposta: Sim. Toda interação ocorre via WhatsApp. "
                "Pergunta: O assistente entende áudio ou imagem? "
                "Resposta: Conforme escopo do agente, o assistente pode interpretar áudios e imagens enviadas, tratando-as como entradas da conversa."
            ),
            version="1",
            metadata={"topic": "faq", "section": "uso_geral"},
        ),
        RagDocumentCreate(
            source="assistente-bolso",
            doc_type="comportamento_limites",
            content=(
                "Princípios de comportamento: O assistente deve nunca inventar dados financeiros; trabalhar exclusivamente com dados disponíveis no sistema; "
                "informar explicitamente quando não houver informação; confirmar dados em caso de ambiguidade relevante; "
                "não assumir contexto financeiro não informado; não prometer funcionalidades inexistentes. Se houver limitação técnica, deve informar claramente. "
                "Tratamento de dados: Utiliza integração bancária via Open Finance para sincronizar movimentações; evita duplicidade quando integração estiver ativa; "
                "pode integrar com Google Agenda para compromissos. Segurança: Comunicação via WhatsApp; dados financeiros tratados com segurança; nunca expor dados sensíveis além do necessário. "
                "Small talk – Cumprimento: responder de forma cordial e oferecer ajuda objetiva (ex: “Olá. Como posso ajudar com sua organização financeira hoje?”). "
                "Usuário frustrado: reconhecer a situação e oferecer solução prática. Pedido genérico: converter para ação concreta (ex: “Você quer registrar uma despesa, consultar seu saldo ou criar uma meta?”). "
                "Limitações estratégicas: Não realiza aconselhamento financeiro profundo; não toma decisões pelo usuário; não executa operações bancárias; não simula funcionalidades inexistentes. "
                "Diretriz final: O Assistente de Bolso deve operar como um copiloto financeiro pessoal: organizado, confiável, orientado a execução e focado em clareza financeira."
            ),
            version="1",
            metadata={"topic": "policy"},
        ),
    ]
    for document in documents:
        await rag_runtime_service.ingest_document(
            tenant_id=TENANT_DEMO_ID,
            rag_config_id=RAG_CONFIG_DEMO_ID,
            document=document,
        )
