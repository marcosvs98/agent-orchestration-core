1-contexto-e-tese-do-servico.md
2-fronteiras-de-responsabilidade-e-nao-objetivos.md
3-modelo-mental-e-vocabulario-canonico.md
4-arquitetura-logica-e-separacao-authoring-runtime.md
5-modelo-relacional-e-entidades-fundamentais.md
6-estrategia-de-isolamento-multi-tenant.md
7-especificacao-rest-e-contratos-de-api.md
8-runtime-de-fluxo-e-mecanismo-de-execucao.md
9-deteccao-de-intencao-e-slot-filling.md
10-orquestracao-de-tools-e-efeitos-colaterais.md
11-ia-prompts-politicas-e-rag.md
12-canais-eventos-e-integracao-externa.md
13-observabilidade-auditoria-e-billing.md
14-seguranca-limites-e-hardening.md
15-evolucao-versionamento-e-governanca-de-mudanca.md
Segue um **README canônico**, pensado para orientar um planejador (humano ou MCP Host) a **ler na ordem correta, com o modelo mental certo**, e evitar interpretações erradas.

---

# Agent Orchestration Core — Planning Guide

Este diretório contém o **planejamento canônico** do serviço *Agent Orchestration Core*.

O objetivo destes documentos **não é implementação**, e sim **alinhamento conceitual absoluto**.
Se o entendimento falhar aqui, qualquer código gerado depois estará estruturalmente errado.

Leia **na ordem**. Não pule etapas.

---

## Como usar este planning

Este material foi desenhado para:

* Alinhar o modelo mental de planejadores, arquitetos e MCP Hosts (Cursor, Claude, etc.)
* Definir fronteiras claras antes de qualquer geração de código
* Evitar acoplamento prematuro, decisões implícitas ou “magia” arquitetural

**Regra de ouro:**

> Se um conceito não está definido aqui, ele não existe no sistema.

---

## Estrutura do planejamento

### Fundamentos conceituais (leitura obrigatória antes de qualquer coisa)

**1-contexto-e-tese-do-servico.md**
Define o que o serviço é e o que ele *não é*. Estabelece o problema resolvido, a tese central e os princípios inegociáveis.

**2-fronteiras-de-responsabilidade-e-nao-objetivos.md**
Delimita responsabilidades do core e explicita anti-objetivos. Evita creep funcional.

**3-modelo-mental-e-vocabulario-canonico.md**
Vocabulário oficial do sistema. Termos como *flow*, *node*, *agent*, *tool*, *run* têm significado preciso. Não invente sinônimos.

---

### Arquitetura e dados (base estrutural)

**4-arquitetura-logica-e-separacao-authoring-runtime.md**
Explica a separação entre definição e execução. Aqui nasce a previsibilidade do sistema.

**5-modelo-relacional-e-entidades-fundamentais.md**
Esqueleto relacional do banco. Entidades, relações e responsabilidades. Campos são detalhe posterior.

**6-estrategia-de-isolamento-multi-tenant.md**
Tenant como fronteira soberana. Identidade, isolamento e governança por design.

---

### Contratos externos e runtime

**7-especificacao-rest-e-contratos-de-api.md**
Superfície REST do serviço. Mesmo endpoints não implementados devem existir (405). Contrato vem antes do código.

**8-runtime-de-fluxo-e-mecanismo-de-execucao.md**
Como flows são executados, como nodes avançam e como o estado é mantido.

---

### Inteligência, decisão e ação

**9-deteccao-de-intencao-e-slot-filling.md**
Processo de entendimento do usuário baseado em tools, schemas e exemplos. IA sob contrato.

**10-orquestracao-de-tools-e-efeitos-colaterais.md**
Execução de integrações externas. Onde efeitos colaterais acontecem — e onde não.

**11-ia-prompts-politicas-e-rag.md**
Papel exato da IA: prompts versionados, políticas de execução, uso controlado de RAG.

---

### Integração, operação e governança

**12-canais-eventos-e-integracao-externa.md**
Canais são adapters. O core processa eventos, não conversa.

**13-observabilidade-auditoria-e-billing.md**
Eventos, métricas, auditoria e custo como cidadãos de primeira classe.

**14-seguranca-limites-e-hardening.md**
Segurança estrutural: identidade, policies, limites e contenção de falhas.

**15-evolucao-versionamento-e-governanca-de-mudanca.md**
Como o sistema evolui sem quebrar execução, contratos ou confiança.

--

**17-roadmap-de-implementacao-inicial.md**
Define a sequência de implementação incremental do core: flows básicos, nodes sequenciais, agents estáticos, tool binding inicial. Foco em scaffolding e execução mínima viável.

**18-versionamento-de-artifacts-e-hash-ids.md**
Detalha o versionamento granular: como flows, nodes, prompts, policies e schemas geram hashes únicos e IDs imutáveis. Define política de snapshot e publicação.

**19-strategy-rollout-e-canary.md**
Como ativar novas versões de forma gradual: total, parcial, por canal ou percentual. Define monitoramento de falhas e rollback seguro sem migração.

**20-execucao-paralela-e-concorrencia.md**
Gerenciamento de múltiplos runs simultâneos, isolamento de threads/processos e limites de recursos. Inclui escalabilidade vertical e horizontal.

**21-integracao-com-IA-e-pipeline-de-intencoes.md**
Ponto de integração com motores de IA (OpenAI, LangGraph, LangFuse). Define contratos, schemas, fallback e versionamento de prompts e políticas de execução.

**22-orquestracao-de-effects-e-tools-complexas.md**
Execução de actions e efeitos colaterais: binding de tools, retries, compensações, idempotência. Define regras de isolamento entre effects e flows.

**23-monitoramento-observabilidade-e-alertas.md**
Métricas, logging estruturado, auditoria de execução, custos, SLA, alertas e tracing distribuído. Inclui integração com dashboards externos.

**24-governanca-de-dados-e-compliance.md**
Regras de retenção de dados, anonimização, auditoria, histórico de execuções e requisitos legais/contratuais. Controles multi-tenant explícitos.

**25-fase-de-hardening-e-seguranca-avancada.md**
Segurança estrutural completa: identidade, policies de acesso, limites por tenant, contenção de falhas, rate-limiting, autenticação e autorização por camada.

**26-estrategia-de-testes-automatizados.md**
Testes de regressão, unitários, de integração e de stress. Validação de flows, nodes, prompts e tools antes da publicação. Testes de rollback e compatibilidade.

**27-roadmap-de-evolucao-continuada.md**
Planejamento de releases futuros: novas features, breaking changes, depreciação de versões antigas. Políticas de manutenção e upgrade incremental.

---


---

## Ordem não é opcional

Este planning foi escrito de forma **progressiva**.
Pular documentos causa lacunas conceituais graves.

Para MCP Hosts:

> Gere artefatos **somente após** processar todos os documentos.

---

## Próximo passo após o planning

Com este material completo, o sistema está pronto para:

* Especificação detalhada de banco (campos, índices)
* Definição formal de schemas
* Geração de código scaffolding
* Implementação incremental e segura

Planejamento encerrado.
Daqui em diante, tudo é execução controlada.
