Segue uma **versão aprimorada e mais precisa** do Planning (10), mantendo 100% do conteúdo já definido, porém com linguagem mais normativa, menos ambiguidade e mais força de contrato arquitetural.

---

## Planning (10) — Execução e Ciclo de Vida de um Run

Objetivo: **definir de forma inequívoca como o sistema executa**, do primeiro evento até o encerramento final, eliminando qualquer comportamento implícito, heurística escondida ou decisão não auditável.

Este planning é **crítico para a integridade do runtime**.
Se o MCP Host errar aqui, o sistema deixa de ser determinístico, auditável e reproduzível.

---

### Tese central

A execução é:

• **Determinística na estrutura**
• **Probabilística apenas na inferência de IA**

O grafo controla:
• ordem
• transições
• limites
• estados

A IA **não controla fluxo**, **não escolhe caminho** e **não altera estrutura**.
Ela apenas produz sinais dentro de contratos explícitos.

---

### Tipos de execução (hierarquia de runs)

A execução é composta por runs com identidade própria e relação hierárquica clara:

• **FlowRun** — execução macro de um FlowVersion
• **NodeRun** — execução de um Node específico
• **AgentRun** — execução cognitiva controlada
• **ToolRun** — efeito colateral externo explícito

Regras:
• nenhum run existe sem seu pai
• nenhum run altera diretamente o estado do pai
• progressão ocorre apenas via eventos persistidos

---

### Estados canônicos (máquina de estados fechada)

#### FlowRun

• CREATED — criado, não validado
• RUNNING — execução ativa
• WAITING — bloqueado por dependência externa explícita
• COMPLETED — término canônico do fluxo
• FAILED — erro não recuperável conforme policy
• ESCALATED — controle transferido para humano ou sistema externo

---

#### NodeRun

• PENDING — elegível para execução
• RUNNING — em execução
• SKIPPED — não executado por decisão de regra
• COMPLETED — execução bem-sucedida
• FAILED — falha sem resolução local

Retry **nunca reaproveita NodeRun**.
Retry = novo NodeRun.

---

#### AgentRun

• CREATED — pronto para execução
• RUNNING — inferência em andamento
• COMPLETED — output válido produzido
• FAILED — erro, timeout ou violação de policy

AgentRun **nunca decide transição de grafo**.

---

#### ToolRun

• CREATED — definido, ainda não executado
• EXECUTING — chamada externa em andamento
• SUCCESS — resposta válida
• ERROR — erro funcional
• TIMEOUT — quebra de SLA

ToolRun **nunca altera GraphState diretamente**.

---

### Fluxo de execução detalhado

1. **Criação**
   • Canal chama Execution API
   • FlowRun criado com referências explícitas de versão
   • Estado inicial = CREATED

2. **Inicialização**
   • Validação de compatibilidade entre versões
   • GraphState inicial criado
   • FlowRun → RUNNING

3. **Execução de Node**
   • NodeRun criado
   • Tipo do node define a estratégia:
   – determinística
   – cognitiva (IA)
   – integração externa (tool)

4. **Execução de IA (quando aplicável)**
   • AgentRun criado
   • AIExecutionPolicy aplicada
   • Prompt resolvido
   • RAG acionado se configurado

5. **Decisão**
   • Resultado do AgentRun persiste no GraphState
   • RoutingRule é avaliada com base no estado

6. **Execução de Tool (quando aplicável)**
   • ToolRun criado
   • Request montado via schema declarado
   • Execução controlada e auditável

7. **Resposta**
   • Resultado formatado pelo agente
   • Evento emitido para o canal de origem

8. **Transição**
   • Próximo Node determinado por RoutingRule
   • Loop continua até estado terminal

---

### Estado WAITING

WAITING **não é estado genérico de pausa**.

Só é permitido quando:
• input humano explícito é necessário
• confirmação externa é exigida
• webhook externo precisa retornar

Requisitos obrigatórios:
• causa explícita
• identificador de correlação
• timeout configurado

Nenhuma execução fica em WAITING indefinidamente.

---

### Tratamento de erros

Erro **não implica encerramento automático**.

A reação ao erro é definida por policy:

• retry (novo run)
• fallback (outro node)
• escalation
• fail-fast

Código **não decide estratégia**.
Policy decide.

---

### Escalonamento

Escalonamento é **parte modelada do sistema**, não exceção.

Características:
• Node ou Policy explícitos
• Evento persistido
• Auditável e reproduzível

Nunca:
• hard-coded
• decisão ad-hoc
• bypass de fluxo

---

### Persistência e replay

Regras invariáveis:

• toda transição gera ExecutionEvent
• GraphState evolui incrementalmente
• nenhum dado é sobrescrito

Resultado:
Execução totalmente **replayable**, **auditável** e **debugável via dados**.

---

### Concorrência e consistência

• Um FlowRun executa apenas um Node por vez
• Paralelismo só existe se o grafo modelar isso
• Locks são por FlowRun, nunca globais

Sem:
• race condition silenciosa
• execução concorrente implícita

---

### Anti-patterns proibidos

• Execução síncrona acoplada ao canal
• Loops “while true” sem estado persistido
• IA decidindo próximo node
• Tool mutando GraphState diretamente

---