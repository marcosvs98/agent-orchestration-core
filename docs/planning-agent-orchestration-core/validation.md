## Objetivo do plano de validação

Confirmar que o sistema:

• é determinístico
• é auditável
• é isolado por tenant
• é governável
• é seguro por padrão
• é evolutivo sem quebra
• é monetizável com precisão

Se qualquer eixo falhar, o sistema **não está pronto para escala**.

---

## Estrutura do plano

Validação em **7 blocos**, cada um com critérios objetivos de aceite.

---

## 1. Validação de Core Runtime e Execução (Plannings 1–6)

### O que validar

• FlowRun executa sem depender de canal
• Grafo executa conforme definição versionada
• Nenhuma regra vive fora do core

### Cenários mínimos

• Mesmo Interaction → mesmo FlowRun (determinismo estrutural)
• Execução parcial interrompida → estado final consistente
• Replay de Interaction → novo FlowRun, mesma sequência lógica

### Critério de aceite

✔ Dois replays produzem a **mesma topologia de eventos**
✘ Qualquer branching implícito reprova

---

## 2. Validação de Estados Canônicos e Transições (Plannings 6, 10)

### O que validar

• Estados são finitos e explícitos
• Transições inválidas são bloqueadas
• Estados não são “interpretativos”

### Cenários mínimos

• Forçar erro de IA
• Forçar erro de tool
• Forçar policy deny

### Critério de aceite

✔ Estado final sempre conhecido (Completed / Failed / Escalated)
✘ Estado “indefinido” ou implícito reprova

---

## 3. Validação de Canais e Adapters (Planning 12)

### O que validar

• Canal não injeta regra
• Adapter só normaliza e persiste
• Core ignora origem

### Cenários mínimos

• HTTP Adapter
• Stub WhatsApp Adapter

### Critério de aceite

✔ Core não sabe qual canal originou
✘ Qualquer if(channel) no core reprova

---

## 4. Validação de Eventos, Observabilidade e Auditoria (Planning 13)

### O que validar

• Evento como fonte primária da verdade
• Correlação completa
• Ordem causal determinística

### Cenários mínimos

• Execução completa
• Execução com falha
• Replay comparativo

### Critério de aceite

✔ Responder “por que isso aconteceu?” só consultando dados
✘ Dependência de log textual reprova

---

## 5. Validação de Billing e Custo (Planning 13)

### O que validar

• Custo registrado em tempo de execução
• Não duplicar custo em replay
• Agregação correta por tenant

### Cenários mínimos

• 1 FlowRun simples
• 1 FlowRun com tool
• 1 replay

### Critério de aceite

✔ Billing = soma exata dos runs
✘ Cálculo offline reprova

---

## 6. Validação de Segurança, Limites e Isolamento (Planning 14)

### O que validar

• Fail-closed em tudo
• Menor privilégio real
• Limites efetivos

### Cenários mínimos

• Token inválido
• Scope insuficiente
• Loop intencional
• Tool lenta

### Critério de aceite

✔ Execução bloqueada + evento registrado
✘ “Passou mesmo assim” reprova

---

## 7. Validação de Versionamento e Governança de Mudança (Planning 15)

### O que validar

• Imutabilidade real
• Publish ≠ Activate
• Rollback sem migração

### Cenários mínimos

• Editar flow publicado
• Ativar versão nova parcialmente
• Reverter versão ativa

### Critério de aceite

✔ Runtime nunca quebra execução ativa
✘ Hotfix em produção reprova

---

## Artefatos obrigatórios ao final da validação

Se não existir, o plano não foi concluído:

• Documento de **event taxonomy final**
• Checklist de **hard limits aplicados**
• Diagrama real de **runtime execution**
• Evidência de **replay auditável**
• Relatório simples de **custo por tenant**

---

## Resultado esperado (estado validado)

Ao final:

• O sistema se explica sozinho
• O runtime é previsível
• O custo é controlável
• A mudança é governada
• O erro é contido

Você não tem um produto.
Você tem uma **plataforma pronta para operar risco**.

---