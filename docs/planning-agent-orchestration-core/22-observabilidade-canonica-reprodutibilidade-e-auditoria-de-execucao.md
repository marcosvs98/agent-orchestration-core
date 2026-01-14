Segue o **P23 em formato de planning**, no mesmo padrão do P22, porém aprofundando **integração com LLM, orquestração lógica e controles críticos de runtime**. Vou direto ao ponto.

---

P23 — **LLM Integration, Prompt Execution & Policy-Aware Runtime**

Objetivo
Estabelecer a camada canônica de integração com LLMs, garantindo execução determinística, auditável, governada por políticas e desacoplada de vendor. O P23 transforma “chamada de modelo” em **capability de runtime**, não em detalhe de infraestrutura.

Objetivo final
Permitir que qualquer Flow/Agent execute chamadas LLM de forma padronizada, observável, versionada, policy-aware e substituível (OpenAI, Azure, Anthropic, local), sem impacto no core do sistema.

---

Escopo do P23
O P23 **não é apenas integração com LLM**. Ele introduz:

• Abstração canônica de execução LLM
• Contrato de prompt estruturado
• Controle de políticas (P21/P22) durante inferência
• Emissão de execution_events ricos
• Base para streaming, tools e reasoning steps futuros

---

Componentes a criar / evoluir

1. LLMProvider (abstração)

Criar uma interface única de provider, por exemplo:

• generate()
• stream()
• supports_tools
• supports_json_schema
• supports_reasoning

Cada provider concreto (OpenAI, Azure, etc.) implementa essa interface.

Ponto crítico:
Nenhuma parte do sistema chama SDK de LLM diretamente. Tudo passa pelo LLMProvider.

Isso elimina lock-in e permite fallback e circuit breaker no nível certo.

---

2. LLMExecutionContext

Objeto canônico passado para qualquer execução LLM.

Contém:
• tenant_id
• flow_run_id
• trace_id
• agent_id
• model_config (modelo, temperatura, max_tokens etc.)
• policy_snapshot (resolvida no início da execução)
• prompt_contract (ver abaixo)

Esse contexto é **imutável durante a execução**.

Motivo: auditabilidade e reexecução determinística.

---

3. Prompt Contract (estrutura canônica)

Definir um formato estruturado de prompt, não string solta.

Exemplo conceitual:

• system_instructions
• developer_instructions
• user_input
• memory_context (RAG / histórico)
• tools_schema (se aplicável)
• output_constraints (JSON schema, formato, etc.)

Nada de concatenar strings no runtime.

Vantagem:
• previsibilidade
• validação
• versionamento
• diff entre execuções

---

4. PromptVersion

Criar entidade/versionamento lógico do prompt.

• prompt_id
• version
• hash
• content_struct (JSON)
• created_at

Flows/Agents sempre referenciam **prompt_id + version**.

Isso permite:
• rollback
• A/B test
• replay exato

---

5. LLMExecutionService (core do P23)

Serviço responsável por:

1. Receber LLMExecutionContext
2. Validar policy (P21):
   • modelo permitido?
   • custo máximo?
   • tools permitidas?
3. Resolver provider + modelo
4. Executar chamada
5. Emitir execution_events (P22)
6. Retornar resposta normalizada

Esse serviço **não conhece Flow nem Session**, apenas execução LLM.

---

6. Execution Events específicos de LLM

Padronizar eventos como:

• LLM_REQUESTED
• LLM_POLICY_VALIDATED
• LLM_PROVIDER_SELECTED
• LLM_RESPONSE_RECEIVED
• LLM_RESPONSE_PARSED
• LLM_EXECUTION_FAILED

Payload sempre estruturado, sem texto livre.

Exemplo de payload:
• model
• provider
• tokens_in
• tokens_out
• latency_ms
• cost_estimate

Esses eventos alimentam observabilidade, billing e debugging.

---

7. Output Normalization

Toda resposta LLM vira um formato canônico:

• raw_text
• structured_output (se JSON)
• tool_calls (se houver)
• finish_reason
• usage

Nenhuma camada acima lê resposta “crua” do provider.

---

8. Erros e falhas controladas

Definir taxonomia clara:

• PolicyViolationError
• ProviderTimeoutError
• InvalidOutputError
• RateLimitError

Todos os erros:
• geram execution_event
• carregam trace_id
• nunca vazam stacktrace para cima

---

9. Circuit Breaker (integração com P21)

Antes de executar:
• checar breaker por tenant + provider + model

Após falha:
• registrar falha
• avaliar abertura do breaker

Isso evita cascata de erro em LLM instável.

---

10. Preparação para próximos planos

O P23 **deixa ganchos prontos** para:

• streaming de tokens (P24)
• tool calling orchestration
• reasoning steps / scratchpad isolado
• fallback multi-provider
• caching semântico

Nada disso é implementado agora, mas o design já suporta.

---

Critérios de aceite do P23

• Nenhuma chamada direta a SDK de LLM fora do LLMProvider
• Toda execução LLM gera execution_events completos
• Prompt é versionado e estruturado
• Policy é validada antes da inferência
• Provider pode ser trocado sem mudar Flow/Agent
• Execução é reproduzível via trace_id

---
Segue o **trecho isolado**, escrito para ser encaixado **imediatamente antes do resumo executivo do P23**. Texto técnico, direto e reutilizável em planning/spec.

---

Interface, Adaptadores e Integração LLM

A integração com LLM será estruturada em três camadas explícitas: **Interface Canônica**, **Adaptadores de Provider** e **Serviços de Uso (Capabilities)**. Essa separação é intencional e evita acoplamento entre lógica de negócio e fornecedor de modelo.

A Interface Canônica (LLMProvider)

A interface define o contrato mínimo que qualquer motor de IA deve cumprir. Ela não reflete SDKs de mercado, e sim as necessidades do runtime.

Responsabilidades:
• expor capacidades (chat, completion, embedding, moderation)
• executar inferência de forma síncrona ou streaming
• retornar respostas normalizadas
• expor metadados de custo, tokens e latência

Operações típicas da interface:
• chat(prompt_contract, execution_context)
• complete(prompt_contract, execution_context)
• embed(texts[], execution_context)
• moderate(content, execution_context)
• capabilities()

A interface **não recebe strings soltas**, apenas contratos estruturados.
Ela **não decide política**, apenas executa.

---

Adaptadores de Provider

Cada provider (OpenAI, Azure OpenAI, Anthropic, local) implementa a interface canônica via um adaptador.

Responsabilidades do adaptador:
• mapear prompt_contract → payload do provider
• traduzir resposta do provider → formato canônico
• tratar peculiaridades de SDK (retry, headers, timeouts)
• esconder diferenças de API e modelo

O adaptador:
• nunca acessa banco
• nunca aplica política
• nunca conhece Flow ou Agent

Ele é substituível por configuração.

Isso permite:
• troca de vendor sem refatoração
• fallback entre providers
• coexistência multi-provider por tenant

---

Camada de Integração (LLMExecutionService)

O LLMExecutionService orquestra a execução, mas não implementa inferência.

Fluxo resumido:

1. Recebe ExecutionContext + PromptContract
2. Resolve política ativa (modelo, limites, moderação)
3. Seleciona provider e adaptador compatível
4. Invoca método correto da interface
5. Normaliza saída
6. Emite execution_events

Essa camada é onde governança e observabilidade vivem.

---

Atendimento aos principais casos de uso

Conversação (Chat)

• Usa método chat()
• PromptContract inclui:
– system / developer / user
– histórico resumido ou completo
• Resposta retorna:
– mensagem final
– usage
– finish_reason

Permite:
• agentes conversacionais
• assistentes por Flow
• múltiplos estilos de resposta por policy

---

Moderação

• Usa método moderate()
• Executado:
– antes da chamada LLM (input)
– depois da resposta (output)

A política define:
• modelos de moderação
• thresholds
• ações (bloquear, sanitizar, logar)

Moderação **não é responsabilidade do Flow**, e sim do runtime.

---

Embeddings

• Usa método embed()
• Input: lista de textos normalizados
• Output: vetores + metadados

Integração direta com:
• RAG
• busca semântica
• clustering
• deduplicação

O ExecutionContext garante:
• isolamento por tenant
• rastreabilidade
• controle de custo

---

Completions / Jobs Não Conversacionais

• Usa método complete()
• Ideal para:
– classificação
– sumarização
– extração estruturada
– batch jobs

O contrato de saída pode exigir JSON schema validado.

---

Evolução futura sem quebra

Essa arquitetura permite, sem ruptura:

• streaming de tokens
• tool calling / function calling
• reasoning steps isolados
• cache semântico
• fallback automático
• execução paralela multi-modelo

Tudo isso sem alterar Flows, Agents ou domínio.

---

Resumo técnico desse trecho

A interface LLM padroniza **o que o sistema espera da IA**.
Os adaptadores lidam com **como cada fornecedor funciona**.
A integração governa **quando, por que e sob quais regras a IA executa**.

É isso que transforma LLM em infraestrutura crítica — não em dependência frágil.

---

Resumo executivo (bem direto)

P23 transforma LLM de “API externa” em **componente de runtime governado**.
Depois dele, o sistema **controla** o modelo — e não o contrário.

Se quiser, o próximo passo natural é eu te entregar:
• diagrama de sequência do P23
• contrato JSON do Prompt
• interface exata do LLMProvider
• ou já avançar para o P24 (streaming + tool calls)
