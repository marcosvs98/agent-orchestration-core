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

_UORA_SEMANTIC_ALIASES_PT: dict[str, str] = {
    "dashboard_get_overview": (
        "visão geral financeira, painel, dashboard, resumo do mês, como estou financeiramente, "
        "panorama das minhas finanças, situação geral, me dá um overview, consolidado."
    ),
    "list_user_transactions": (
        "consultar extrato, ver lançamentos, mostrar movimentações, listar transações, "
        "ver histórico de gastos, mostrar últimas compras, o que eu gastei, exibir movimentos da conta, "
        "ver todas as transações, filtrar período, buscar transação, pesquisar no extrato. "
        "ATENÇÃO: esta tool é apenas para CONSULTAR e VER transações existentes. "
        "NÃO usar para registrar, criar, lançar ou adicionar transações novas."
    ),
    "create_manual_transaction": (
        "registrar transação, criar transação manual, lançar despesa, adicionar receita, "
        "anotar gasto, incluir compra, registrar pagamento, inserir lançamento, cadastrar movimento, "
        "registre uma transação, registre um gasto, registre uma despesa, crie uma transação, "
        "quero registrar, quero lançar, quero anotar, adicionar transação, nova transação, "
        "gastei X reais, paguei X reais, comprei algo, recebi X reais, entrou X reais, "
        "despesa em dinheiro, compra que não veio do banco, lançamento manual, gasto manual. "
        "ATENÇÃO: esta é a tool correta quando o utilizador quer CRIAR, REGISTRAR, LANÇAR ou "
        "ADICIONAR uma transação nova — NÃO confundir com listar ou consultar transações."
    ),
    "list_similar_transactions": (
        "transações parecidas, gastos similares, outras no mesmo local, compras iguais, "
        "recorrência parecida, lançamentos semelhantes."
    ),
    "get_transaction_detail": (
        "detalhe de uma transação, informações do lançamento, abrir uma movimentação específica, "
        "o que foi essa compra, explicar essa transação, dados completos do lançamento."
    ),
    "spending_by_category": (
        "gastos por categoria, quanto gastei em cada rubrica, ranking de categorias, onde mais gastei, "
        "distribuição de despesas, top categorias, relatório por categoria, alocação do orçamento."
    ),
    "installments_get_summary": (
        "resumo de parcelas, total parcelado, quanto falta parcelar, visão de parcelamento, "
        "compromisso com parcelas, soma das prestações."
    ),
    "list_user_installments": (
        "minhas parcelas, compras parceladas, lista de prestações, parcelas ativas, "
        "carnê, o que estou pagando parcelado."
    ),
    "list_detected_recurring_subscriptions": (
        "assinaturas detectadas, mensalidades recorrentes, serviços que cobram todo mês, "
        "Netflix Spotify estilo cobrança fixa, gastos recorrentes identificados."
    ),
    "list_user_credit_cards": (
        "meus cartões, cartões cadastrados, lista de cartões de crédito, "
        "quais cartões tenho, plasticópes."
    ),
    "cards_get_invoice_evolution": (
        "evolução da fatura, histórico de fatura do cartão, como a fatura variou, "
        "tendência de fechamento, fatura mês a mês."
    ),
    "cards_get_invoice_totals": (
        "totais de fatura, soma das faturas, total a pagar nos cartões, "
        "fechamento consolidado de faturas."
    ),
    "get_credit_card_detail": (
        "detalhe do cartão, dados do cartão X, limite, melhor dia, informações do plastic, "
        "resumo de um cartão específico."
    ),
    "list_card_invoices": (
        "faturas do cartão, fechamentos anteriores, lista de faturas de um cartão, "
        "histórico de invoices, qual fechamento."
    ),
    "list_invoice_transactions": (
        "lançamentos da fatura, gastos nesse fechamento, movimentos da invoice, "
        "o que entrou na fatura, itens da fatura."
    ),
    "list_user_wallets": (
        "carteiras, contas, saldos por instituição, minhas contas conectadas, "
        "onde tenho dinheiro, lista de carteiras."
    ),
    "financial_health_get_current_score": (
        "score de saúde financeira, nota atual, como está minha saúde financeira, "
        "pontuação financeira, rating de finanças."
    ),
    "financial_health_get_score_history": (
        "histórico do score, evolução da saúde financeira, score no tempo, "
        "como minha nota mudou."
    ),
    "financial_health_get_score_explanation": (
        "por que meu score é assim, explicação da nota, fatores do score, "
        "entender a saúde financeira, detalhamento do cálculo."
    ),
    "financial_health_get_action_plan": (
        "plano de ação financeira, o que fazer para melhorar, recomendações, "
        "passos sugeridos, dicas personalizadas para subir score."
    ),
    "investments_get_portfolio_summary": (
        "resumo da carteira de investimentos, patrimônio investido, visão geral dos investimentos, "
        "consolidado de ativos, quanto tenho aplicado."
    ),
    "investments_list_positions": (
        "posições, ativos que tenho, detalhe da carteira, cada investimento, "
        "lista de tickers ou fundos, composição da carteira."
    ),
    "investments_get_insights": (
        "insights de investimento, análise da carteira, comentários sobre alocação, "
        "visão de performance relativa ao portfólio."
    ),
    "market_get_indices": (
        "índices de mercado, Ibovespa e afins, como fechou o índice, "
        "cotação de índice, mercado em alta ou baixa."
    ),
    "market_get_quotes": (
        "cotação de ativo, preço da ação, quote ao vivo, "
        "quanto está valendo hoje, ticker."
    ),
    "market_get_news_headlines": (
        "notícias de mercado, manchetes financeiras, headlines, "
        "news do mercado, o que saiu na imprensa sobre finanças."
    ),
    "advisor_client_360_alerts": (
        "alertas do cliente na visão 360, red flags, riscos e alertas do assessorado, "
        "avisos importantes sobre o cliente."
    ),
    "advisor_client_360_behavior": (
        "comportamento de gastos do cliente, padrão de consumo do cliente 360, "
        "hábitos financeiros do assessorado."
    ),
    "advisor_client_360_cash_flow": (
        "fluxo de caixa do cliente, entradas e saídas do assessorado, "
        "movimento de caixa na visão 360."
    ),
    "advisor_client_360_debt_evolution": (
        "evolução da dívida do cliente, histórico de endividamento, "
        "como a dívida mudou no tempo."
    ),
    "advisor_client_360_debts": (
        "dívidas do cliente, passivos do assessorado, o que o cliente deve, "
        "consolidado de empréstimos e financiamentos."
    ),
    "advisor_client_360_list_goals": (
        "metas financeiras do cliente, objetivos do assessorado, "
        "planos e metas na visão 360."
    ),
    "advisor_client_360_investments": (
        "investimentos do cliente, carteira do assessorado, "
        "alocação de investments na visão 360."
    ),
    "advisor_client_360_summary": (
        "resumo 360 do cliente, visão geral do assessorado, snapshot do cliente, "
        "panorama advisor 360."
    ),
    "advisor_client_360_timeline": (
        "linha do tempo financeira do cliente, histórico cronológico, "
        "eventos e marcos do assessorado."
    ),
}


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
    if oid in _UORA_SEMANTIC_ALIASES_PT:
        return _UORA_SEMANTIC_ALIASES_PT[oid]
    tool_name = str(row["tool_name"])
    path = str(row["path"])
    method = str(row.get("method") or "GET").upper()
    su = row.get("summary")
    if method == "GET":
        verb_phrase = f"{tool_name} consulta GET"
        pt_hints = (
            "pedidos em português: mostrar, listar, quero ver, me mostra o, qual o, preciso saber"
        )
    else:
        verb_phrase = f"{tool_name} operação HTTP {method} (criar, atualizar ou remover conforme o caso)"
        pt_hints = (
            "pedidos em português: registrar, criar, adicionar, lançar, atualizar, remover, quero que você"
        )
    bits = [verb_phrase, f"caminho {path}", pt_hints]
    if su:
        bits.append(str(su))
    return ". ".join(bits)


def _spending_by_category_cluster_docs(row: dict[str, Any]) -> list[RagDocumentCreate]:
    m = _tool_catalog_meta(row)
    tool_name = str(row["tool_name"])
    oid = str(row["operation_id"])
    return [
        RagDocumentCreate(
            source="tool_catalog",
            doc_type="tool_catalog",
            version=f"{oid}.v1.r",
            content=(
                f"{tool_name} operation. User asks for reports and summaries of spending by "
                "category in Portuguese: resumo dos gastos por categoria, top gastos por categoria, "
                "maiores gastos por categoria, onde mais gastei, em que categoria gastei mais, "
                "ranking de categorias, quanto gastei em cada categoria, distribuição de gastos, "
                "alocação de despesas, relatório de gastos por categoria, visão por categoria do mês, "
                "gastos agrupados por categoria, custo de vida por categoria, comparar categorias."
            ),
            metadata={**m, "cluster": "reports"},
        ),
        RagDocumentCreate(
            source="tool_catalog",
            doc_type="tool_catalog",
            version=f"{oid}.v1.i",
            content=(
                f"{tool_name} for AI insights and narrative: pedido para analisar padrão de consumo, "
                "entender para onde vai o dinheiro, destacar categorias que mais pesam no orçamento, "
                "sugerir foco em categorias altas, pedido de síntese explicativa com totais por "
                "categoria (sem inventar valores — usar dados da API)."
            ),
            metadata={**m, "cluster": "insights"},
        ),
        RagDocumentCreate(
            source="tool_catalog",
            doc_type="tool_catalog",
            version=f"{oid}.v1.m",
            content=(
                f"{tool_name} quando o utilizador menciona período: mês atual, mês passado, YYYY-MM, "
                "este mês, último mês, meses por extenso em português ou inglês com ano "
                "(ex.: março de 2026 → month=2026-03), fechamento mensal, visão do mês. "
                "A API expõe apenas o parâmetro opcional `month` (YYYY-MM), não existe campo `year` separado."
            ),
            metadata={**m, "cluster": "month"},
        ),
    ]


def _create_manual_transaction_cluster_docs(row: dict[str, Any]) -> list[RagDocumentCreate]:
    """RAG clusters for POST /transactions — body fields, PT phrasing, and disambiguation."""
    m = _tool_catalog_meta(row)
    tool_name = str(row["tool_name"])
    oid = str(row["operation_id"])
    return [
        RagDocumentCreate(
            source="tool_catalog",
            doc_type="tool_catalog",
            version=f"{oid}.v1.body",
            content=(
                f"{tool_name} cria um lançamento manual no extrato. Corpo JSON (OpenAPI): "
                "`account_id` (UUID da conta/carteira), `amount_minor` (valor em centavos; ex.: R$ 10,50 → 1050), "
                "`description` (texto livre do lançamento), `category_id` (UUID da categoria), "
                "`booked_on` (data ISO YYYY-MM-DD), `direction` opcional `outflow` ou `inflow` (padrão despesa: outflow), "
                "`currency` opcional (padrão BRL). Não inventar IDs: o utilizador ou contexto deve indicar conta e categoria."
            ),
            metadata={**m, "cluster": "request_body"},
        ),
        RagDocumentCreate(
            source="tool_catalog",
            doc_type="tool_catalog",
            version=f"{oid}.v1.pt",
            content=(
                f"{tool_name} quando o utilizador diz que pagou algo em dinheiro, esqueceu de sincronizar, "
                "quer anotar uma compra ou receita que não veio do Open Finance, ou pede para 'lançar' / 'registrar' "
                "um gasto com valor e descrição. Preferir esta tool em vez de só listar transações."
            ),
            metadata={**m, "cluster": "intent_pt"},
        ),
        RagDocumentCreate(
            source="tool_catalog",
            doc_type="tool_catalog",
            version=f"{oid}.v1.ex",
            content=(
                f"{tool_name} — exemplos de frases reais do utilizador que devem acionar esta tool: "
                "\"Registre uma transação no valor de 50 reais na categoria Supermercado na data de hoje\", "
                "\"Anota aí que gastei 120 reais no mercado\", "
                "\"Lança uma despesa de 200 reais em restaurante\", "
                "\"Adiciona uma receita de 3000 reais de salário\", "
                "\"Registra um gasto de 80 reais em transporte\", "
                "\"Quero registrar que paguei 150 reais na farmácia\", "
                "\"Cria uma transação manual de 500 reais\", "
                "\"Recebi 1000 reais, registra como receita\", "
                "\"Gastei 45 reais no Uber hoje, registra\", "
                "\"Paguei o almoço, 35 reais, anota como alimentação\". "
                "Todas essas frases indicam CRIAÇÃO de transação, NÃO consulta."
            ),
            metadata={**m, "cluster": "user_examples"},
        ),
        RagDocumentCreate(
            source="tool_catalog",
            doc_type="tool_catalog",
            version=f"{oid}.v1.dis",
            content=(
                f"Desambiguação: {tool_name} vs list_user_transactions. "
                "Quando a frase do utilizador contém verbos como REGISTRAR, CRIAR, LANÇAR, ANOTAR, "
                "ADICIONAR, INCLUIR, CADASTRAR ou INSERIR seguidos de transação, gasto, despesa, receita "
                "ou lançamento, a tool correta é create_manual_transaction (POST /api/v1/transactions). "
                "A tool list_user_transactions (GET /api/v1/transactions) serve apenas para CONSULTAR, "
                "VER, LISTAR, MOSTRAR ou BUSCAR transações já existentes. "
                "Regra: verbo de ação/escrita → create_manual_transaction. "
                "Verbo de leitura/consulta → list_user_transactions."
            ),
            metadata={**m, "cluster": "disambiguation"},
        ),
    ]


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
    return uora_allowlisted_tool_catalog_documents(
        [
            {
                "tool_id": tool_id,
                "tool_config_id": tool_config_id,
                "tool_name": "spending_by_category",
                "operation_id": "spending_by_category",
                "method": "GET",
                "path": "/api/v1/spending/by-category",
                "summary": None,
                "description": None,
            }
        ]
    )


def uora_allowlisted_tool_catalog_documents(
    rows: list[dict[str, Any]],
) -> list[RagDocumentCreate]:
    docs: list[RagDocumentCreate] = []
    for row in rows:
        oid = str(row["operation_id"])
        tool_name = str(row["tool_name"])
        m = _tool_catalog_meta(row)
        docs.append(
            RagDocumentCreate(
                source="tool_catalog",
                doc_type="tool_catalog",
                version=f"{oid}.v1.sa",
                content=(
                    f"{tool_name} operation semantic aliases in Portuguese. "
                    f"{_semantic_alias_text(row)}"
                ),
                metadata={**m, "cluster": "semantic_aliases"},
            ),
        )
        parts: list[str] = [tool_name]
        su = row.get("summary")
        if su:
            parts.append(str(su))
        de = row.get("description")
        if de:
            parts.append(str(de))
        docs.append(
            RagDocumentCreate(
                source="tool_catalog",
                doc_type="tool_catalog",
                version=f"{oid}.v1.su",
                content=". ".join(parts),
                metadata={**m, "cluster": "api_summary"},
            ),
        )
        if oid == "spending_by_category":
            docs.extend(_spending_by_category_cluster_docs(row))
        if oid == "create_manual_transaction":
            docs.extend(_create_manual_transaction_cluster_docs(row))
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
            "tool_name": "spending_by_category",
            "operation_id": "spending_by_category",
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
