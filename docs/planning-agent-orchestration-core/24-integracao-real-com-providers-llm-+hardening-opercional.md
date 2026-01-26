## Planning (24) — Integração Real com Providers de LLM + Hardening Operacional

### Objetivo

Conectar o sistema a **LLMs reais (OpenAI, Azure OpenAI, Anthropic, etc.)** de forma **segura, governada e substituível**, usando **exatamente os contratos, políticas e eventos definidos no P23**, sem alterar o core.

P24 **não muda arquitetura**.
P24 **materializa infraestrutura**.

Resumo executivo:

> “No P24, a IA deixa de ser simulada e passa a existir em produção — sem ganhar poder novo.”

---

## Escopo do P24

O P24 cobre:

* Implementação de **Provider Adapters reais**
* Cliente HTTP resiliente
* Mapeamento de modelos reais → modelos lógicos
* Cálculo de custo real
* Integração com secrets / credentials
* Hardening operacional (timeouts, retries, circuit breaker)
* Observabilidade real (latência, erro, custo)
* Feature flags e rollout controlado

O P24 **não cobre**:

* Prompt engineering avançado
* RAG
* Fine-tuning
* Autonomia da LLM
* Decisão de fluxo

---

## Tese central

Providers são **infraestrutura volátil**.
O sistema é **estável**.

Logo:

* Nenhum SDK vaza para o domínio
* Nenhum provider define contrato
* Nenhum detalhe externo quebra determinismo interno

---

## Arquitetura no P24

```
[ Nodes / LLMExecutor ]
           |
           v
   [ P23 Orchestrator ]
           |
           v
[ Provider Registry / Selector ]
           |
           v
[ Provider Adapter Real ]
           |
           v
[ HTTP Client / SDK ]
```

Tudo acima do Adapter **já existe** (P23).
O P24 implementa o que está abaixo.

---

## 1. Provider Adapters Reais

### Providers suportados inicialmente

* OpenAI
* Azure OpenAI (variante de OpenAIAdapter)
* Anthropic (opcional, se fizer sentido)

Cada provider implementa **exatamente** os contratos P23.

Exemplo:

```python
class OpenAITextGenerationAdapter(TextGenerationCapability):

    async def generate(
        self,
        request: TextGenerationRequest,
        policy: GenerationPolicy
    ) -> TextGenerationResult:
        ...
```

Regras duras:

* Adapter **não resolve policy**
* Adapter **não decide retry**
* Adapter **não calcula budget global**
* Adapter **não conhece tenant**

Ele só executa.

---

## 2. Model Mapping (Camada Crítica)

O domínio e os nodes **nunca referenciam modelos reais**.

Eles usam **model_id lógico**:

```
"text-small"
"text-medium"
"text-large"
"embedding-default"
```

### Resolver de modelo (P24)

```python
resolve_model(
  model_id="text-medium",
  provider="openai",
  tenant="your_pypy"
) -> provider_model="gpt-4o-mini"
```

Benefícios:

* troca de modelo sem deploy
* downgrade automático por custo
* rollback instantâneo

Esse mapping vive em config / DB controlado, não em código.

---

## 3. HTTP Client Hardening

Cada adapter usa um **HTTP client padrão corporativo**:

* timeout explícito
* retry com backoff
* circuit breaker
* cancelamento por policy
* idempotency key (quando aplicável)

Exemplo de policy aplicada:

```
timeout_ms: 800
retry_limit: 1
fallback: downgrade_model
```

Nada de defaults de SDK.

---

## 4. Cálculo de Custo Real

No P23 o custo era teórico.
No P24 ele é **real**.

### Fluxo

1. Provider retorna usage (tokens, chars, etc.)
2. Adapter normaliza usage
3. CostEngine aplica tabela de preços
4. Evento é emitido
5. Budget é atualizado

Exemplo:

```
provider=openai
model=gpt-4o-mini
input_tokens=420
output_tokens=120
cost_usd=0.00019
```

Se custo exceder policy:

* chamada é bloqueada **antes**
* ou degradada para modelo inferior

---

## 5. Observabilidade Real (P22 + P23)

P24 **ativa** os eventos definidos antes.

Eventos emitidos:

* LLMCallStarted
* LLMCallCompleted
* LLMCallFailed

Com payload real:

* provider
* model
* latency_ms
* tokens
* cost_usd
* error_code (se houver)

Esses eventos se encaixam na timeline canônica do P22.

---

## 6. Secrets & Credenciais

Nenhum adapter carrega chave hardcoded.

Padrão:

* secrets via Vault / env / secret manager
* resolução por provider + tenant
* rotação sem restart (quando possível)

O Adapter recebe **client já configurado**, não a chave.

---

## 7. Feature Flags e Rollout

Nenhum provider entra “ligado”.

Controles:

* enable_llm_provider_openai = false
* enable_llm_for_tenant_your_pypy = false
* rollout por percentual
* kill switch global

Isso permite:

* canary
* rollback imediato
* teste em produção controlado

---

## 8. Testes no P24

### Tipos de teste

* Unit test de adapter (mock HTTP)
* Contract test contra schema P23
* Failure injection (timeout, 429, 500)
* Cost calculation test
* Policy enforcement test

Fake provider **continua existindo** para testes rápidos.

---

## 9. Erros e Fallback

Erros tratados explicitamente:

* timeout
* rate limit
* schema inválido
* erro de provider
* custo excedido

Todos resultam em:

* LLMCallFailed
* NodeFailed
* edge explícito de erro

Nunca em comportamento implícito.

---

## 10. O que NÃO muda no P24

Importante deixar claro:

* Grafo continua determinístico
* LLM não roteia
* LLM não executa tool
* LLM não decide fluxo
* LLM não persiste estado

Ela só responde ao contrato.

---

## Objetivo final do P24

Ao final do P24, o sistema terá:

* Integração real com LLMs
* Custo real, rastreável e auditável
* Providers plugáveis
* Rollout seguro
* Zero impacto no domínio

Resumo final:

> **P23 define o cérebro.
> P24 conecta os nervos ao mundo real.
> Sem mexer no esqueleto.**

Se quiser, próximo passo pode ser:

* P25 (RAG controlado)
* P26 (Prompt versioning e cache semântico)
* Ou detalhar um adapter OpenAI completo, linha por linha
