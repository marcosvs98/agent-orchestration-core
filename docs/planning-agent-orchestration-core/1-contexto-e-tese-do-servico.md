## Planning (1) — Contexto e Tese do Serviço

### O que é este serviço

Este serviço é uma **plataforma de orquestração cognitiva multi-tenant**, projetada para interpretar entradas em linguagem natural, decidir caminhos de execução e acionar integrações externas de forma controlada, auditável e previsível.

Ele **não é um chatbot**.
Ele **não é um assistente genérico**.
Ele **não é um wrapper de LLM**.

O serviço opera como um **motor de decisão e execução**, onde modelos de IA são usados apenas como componentes cognitivos dentro de fluxos explícitos e versionados.

A linguagem natural é tratada como **input não estruturado** que precisa ser classificado, normalizado e convertido em decisões e dados estruturados antes de qualquer efeito colateral ocorrer.

---

### Qual problema este serviço resolve

Empresas que constroem assistentes baseados em IA enfrentam, de forma recorrente, os mesmos problemas estruturais:

– Lógica de negócio acoplada a prompts
– Fluxos implícitos, impossíveis de auditar ou versionar
– Execução de ações externas decididas diretamente por modelos de IA
– Dificuldade em escalar para múltiplos canais e múltiplos clientes
– Falta de isolamento real entre tenants
– Impossibilidade de reproduzir, debugar ou explicar decisões

Este serviço resolve esses problemas ao **externalizar decisão, execução e governança** para um core determinístico, deixando a IA atuar apenas onde ela agrega valor: interpretação e formatação.

---

### O que o serviço **não faz** (delimitação clara)

Este serviço:

– Não toma decisões finais de negócio com IA
– Não executa chamadas externas diretamente a partir de prompts
– Não mantém “estado conversacional mágico”
– Não depende de um canal específico (WhatsApp, Web, App, Voice)
– Não exige que o domínio de negócio seja conhecido pelo core

Qualquer tentativa de usar o serviço como um “chatbot inteligente” viola o modelo e degrada o sistema.

---

### Princípios não negociáveis

1. **Isolamento por tenant é estrutural**
   Todo dado, decisão e execução pertence a um tenant.
   O tenant é inferido pela identidade autenticada, nunca informado pelo cliente.

2. **Definição é diferente de execução**
   Flows e agentes são definidos e versionados.
   Execuções são rastreadas, auditáveis e nunca alteram a definição original.

3. **IA não executa efeitos colaterais**
   Modelos de IA classificam, extraem, decidem caminhos e formatam respostas.
   Chamadas externas, persistência e integrações são sempre determinísticas.

4. **Tudo é explícito e versionado**
   Fluxos, agentes, prompts, políticas, ferramentas e decisões têm versão.
   Nada relevante é implícito ou mutável em tempo de execução.

5. **Canal é detalhe de entrada e saída**
   O core do sistema é completamente agnóstico ao meio de interação.

---

### Vocabulário canônico (modelo mental comum)

Para evitar ambiguidade, os termos abaixo têm significado preciso e imutável:

– **Flow**: definição lógica de um processo
– **FlowVersion**: snapshot imutável de um flow
– **FlowRun**: execução concreta de uma versão de flow

– **Node**: unidade executável dentro de um flow
– **NodeRun**: execução de um node

– **Agent**: definição lógica de um agente cognitivo
– **AgentVersion**: implementação imutável de um agente
– **AgentRun**: execução efetiva de um agente

– **Tool**: contrato abstrato de integração externa
– **ToolConfig**: configuração concreta de uma tool para um tenant

– **Router**: mecanismo declarativo de decisão de caminho
– **ConditionExpression**: expressão reutilizável de decisão

– **Session / Interaction**: contexto técnico e eventos de entrada/saída
– **GraphState**: estado consolidado da execução de um flow

Esses termos **não são intercambiáveis**.
Usá-los fora desse significado gera erro conceitual.

---

### Objetivo final do serviço (em termos operacionais)

Permitir que empresas construam **assistentes e sistemas orientados a linguagem natural** de forma segura e escalável, sem abrir mão de controle, previsibilidade e governança.

O serviço deve possibilitar:

– Evolução de fluxos sem reimplementar lógica
– Troca de modelos de IA sem refatorar o core
– Execução segura de ações externas baseadas em intenção
– Observabilidade total do que foi decidido, executado e respondido

Este documento define o **modelo mental correto**.
Todo planejamento posterior parte daqui.
