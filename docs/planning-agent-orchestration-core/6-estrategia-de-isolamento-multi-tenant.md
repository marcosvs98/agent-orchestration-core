## Planning (6) — Estados, Idempotência e Consistência de Execução

Objetivo: **garantir execução determinística, auditável e reprocessável**, independente de canal, modelo de IA ou falhas intermediárias.

Aqui se define como o sistema **se comporta sob carga, erro e retry**. Sem isso, o runtime vira caixa-preta.

---

### Princípios não negociáveis

• Execução é **state machine**, não fluxo implícito
• Todo passo gera estado persistido
• Reexecução nunca duplica efeito
• IA **não decide estado final**, apenas produz sugestões
• Side-effects são explicitamente marcados

---

### Entidades de Estado (conceito)

• FlowRun
• NodeRun
• AgentRun
• ToolRun

Cada uma:
• possui status
• possui timestamps
• possui input/output imutáveis
• referencia versão exata do artefato usado

---

### Estados Canônicos

Status base (extensível, mas não inventado):

• CREATED
• QUEUED
• RUNNING
• WAITING_INPUT
• COMPLETED
• FAILED
• CANCELLED

Estado é **dado**, não enum mágico em código.

---

### Idempotência

Obrigatória para:

• POST /flow-runs
• POST /tool-runs

Mecanismo:
• Idempotency-Key no header
• Chave + tenant + endpoint = execução única
• Repetição retorna mesmo resultado

Sem idempotência → não entra em produção.

---

### Reprocessamento

Reprocessar **não é retry cego**.

Modelagem correta:
• Re-run sempre cria nova execução
• Pode referenciar execução anterior
• Nunca sobrescreve estado histórico

Exemplo:
• FlowRun A falhou
• FlowRun B referencia A como origem

Auditoria preservada.

---

### Consistência

Modelo adotado: **eventual consistente com garantias locais**

• Cada NodeRun é atomicamente consistente
• FlowRun é consistente por agregação
• ToolRun pode falhar sem quebrar FlowRun imediatamente

Nada de transação distribuída.

---

### Falhas e Dead Letter

• Falha técnica ≠ falha de negócio
• Toda falha é classificada
• Falhas não recuperáveis vão para DLQ lógico
• DLQ é entidade, não fila invisível

---

### Observabilidade mínima

Obrigatória por contrato:

• correlation_id
• tenant_id
• flow_version
• agent_version
• tool_version

Sem isso, não existe debugging.

---

### Anti-patterns proibidos

• “retry automático infinito”
• reexecução silenciosa
• estado apenas em memória
• logs como fonte de verdade

---
