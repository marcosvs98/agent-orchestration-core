## Planning (12) — Canais, Eventos e Integração Externa (Ajustado)

Objetivo: tratar **entrada e saída como detalhe técnico**, preservando o core como **motor determinístico de processamento de eventos**.

Canal é infraestrutura.
Produto é composição.
Domínio vive no core.

**Estrutura de pastas não define arquitetura. Contratos definem.**

---

## Tese central (reforçada)

O sistema **não mantém conversa**.
O sistema **não expõe o core diretamente**.
O sistema **processa eventos e produz artefatos**.

Nenhum canal — HTTP, WhatsApp, Voice, Batch — **fala com o core diretamente**.

Todo acesso passa por **uma fronteira única e explícita**.

---

## Ponto central da arquitetura (clarificado)

Existe um **único ponto de entrada lógico** no core:

→ **Execution Boundary** (Application / Use Case Layer)

Adapters **nunca**:

* chamam serviços de domínio
* acessam modelos de runtime
* manipulam estado de execução

Eles apenas **publicam eventos de entrada** e **consomem artefatos de saída**.

---

## Modelo mental canônico (sem ambiguidade)

Canal
→ Adapter (Boundary Técnica Externa)
→ Interaction (Evento Persistido)
→ **Execution Boundary**
→ FlowRun (Runtime Determinístico)
→ ResponseArtifact
→ Adapter (Renderização / Dispatch)

Se um Adapter cair:

* nenhuma regra de negócio cai
* nenhum estado interno corrompe
* nenhum fluxo “fica pela metade”

---

## Adapters (Inbound) — Boundary rígida e burra

Adapter é **infraestrutura descartável**.

Responsabilidades **obrigatórias**:

* autenticar / validar assinatura
* normalizar payload
* extrair metadata técnica
* resolver ou criar Session
* persistir Interaction
* **publicar Interaction para execução**

Responsabilidades **proibidas** (reforço):

* chamar ExecutionService diretamente
* decidir fluxo
* inferir intenção
* chamar Agent
* montar prompt
* enriquecer semanticamente input

Regra operacional:

> Adapter só escreve Interaction e solicita execução. Nada além disso.

---

## Interaction — Contrato de entrada (inalterado)

Interaction continua sendo o **único input oficial** do core.

Ela é:

* imutável
* persistida antes de qualquer execução
* versionada por schema
* vinculada a Session e Tenant

Interaction **não depende** de:

* onde o model está declarado
* pasta domain vs infra
* framework web

É um **contrato**, não um arquivo.

---

## Sessions — Continuidade técnica (reforço negativo)

Session **não pertence ao domínio de conversa**.
Session pertence ao **domínio técnico de correlação**.

Ela serve para:

* agrupar Interactions
* manter continuidade de canal
* correlacionar execuções

Ela **não guarda**:

* intenção
* slots
* contexto
* histórico semântico

Se Session virar memória → bug arquitetural.

---

## Core Runtime — FlowRun (ponto isolado)

FlowRun **só nasce** dentro do core.

Canais:

* não criam FlowRun
* não mutam FlowRun
* não “avançam” execução

FlowRun:

* consome Interaction
* executa grafo
* emite eventos
* produz ResponseArtifact

Tudo versionado, auditável e replayable.

---

## Eventos internos — Fonte de verdade

Eventos continuam sendo **first-class**.

Regra dura reforçada:

> Sem evento persistido, o sistema assume que não aconteceu.

Eventos não são logs.
Eventos são **contrato histórico**.

---

## Integração externa (Outbound) — Único ponto permitido

Não muda, mas fica explícito:

**NENHUM Adapter executa Tool.**

Caminho único:
Node
→ AgentRun
→ ToolOrchestrator
→ Executor

Se um Adapter precisar “chamar algo externo”, ele está errado.

---

## ToolOrchestrator — Firewall semântico

Permanece como:

* guardião de timeout
* guardião de retry
* guardião de budget
* normalizador de erro

IA nunca vê erro cru.
IA nunca vê segredo.
IA nunca vê protocolo.

---

## ResponseArtifact — Saída oficial do core (reforço)

ResponseArtifact é:

* o **único output** do core
* independente de canal
* persistido
* versionado
* auditável

Adapter apenas **traduz**.

---

## Organização de código (explicitamente fora do escopo)

Este planning **não exige**:

* criar `domain/conversation/*`
* mover models existentes
* refatorar pastas agora

Ele exige apenas que:

* Interaction seja tratada como contrato
* ResponseArtifact exista como artefato
* Execution Boundary seja respeitada
* Adapters não vazem domínio

Organização física pode evoluir depois **sem quebrar o desenho**.

---

## Anti-patterns proibidos (reforço final)

* Adapter chamando serviço de execução
* Canal decidindo fluxo
* Session como memória
* Prompt dependente de canal
* Tool chamada fora do ToolOrchestrator
* Core retornando string

Quebrou isso → não é bug, é violação de arquitetura.

---

## Fechamento executivo

O ajuste do Planning (12) foi **endurecer as fronteiras**, não criar novas.

A IA se confundiu porque pensou em **pastas**.
Este planning fala de **contratos, limites e isolamento**.

Se amanhã:

* trocar FastAPI por outra coisa
* remover WhatsApp
* adicionar Batch

O core **não muda**.

Esse continua sendo o teste de sanidade do sistema.
