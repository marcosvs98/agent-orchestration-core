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


def demo_assistente_bolso_kb_documents() -> list[RagDocumentCreate]:
    return [
        RagDocumentCreate(
                source="uora",
                doc_type="identity_proposito",
                content=(
                    "Identidade: O Uora é uma IA de controle financeiro pessoal operada via WhatsApp. "
                    "Atua como interface conversacional para organização de receitas, despesas, saldos, metas financeiras. "
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
                source="uora",
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
                source="uora",
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
                source="uora",
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
                source="uora",
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
                source="uora",
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
                source="uora",
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
                source="uora",
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
                source="uora",
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
                    "Diretriz final: O Uora deve operar como um copiloto financeiro pessoal: organizado, confiável, orientado a execução e focado em clareza financeira."
                ),
                version="1",
                metadata={"topic": "policy"},
            ),
    ]


def demo_tool_catalog_seed_documents(
    *,
    tool_id: UUID,
    tool_config_id: UUID,
) -> list[RagDocumentCreate]:
    tid = str(tool_id)
    tcid = str(tool_config_id)
    return [
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
                "tool_id": tid,
                "tool_config_id": tcid,
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
                "tool_id": tid,
                "tool_config_id": tcid,
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
                "tool_id": tid,
                "tool_config_id": tcid,
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
                "tool_id": tid,
                "tool_config_id": tcid,
                "tool_name": "createExpense",
                "operation_id": "createExpense",
                "method": "POST",
                "path": "/createExpense",
                "cluster": "amount_signals",
                "tool_intent": "command",
            },
        ),
    ]


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
        "O Uora é uma IA de controle financeiro pessoal pelo WhatsApp; "
        "organiza receitas, despesas, saldos e metas financeiras."
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
            "tool_name": "createExpense",
            "operation_id": "createExpense",
            "method": "POST",
            "path": "/createExpense",
            "tool_intent": ToolIntentFilter.COMMAND.value,
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
