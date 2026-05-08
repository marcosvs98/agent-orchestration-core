# Evolução do produto

Esta pasta reúne documentos que ligam o **estado atual do código** a **direções de evolução** (produto e arquitetura). O ponto de partida para entender *como o sistema funciona hoje* é sempre o retrato factual no repositório.

## Começar por aqui: estado atual

Leia **[as-is.md](as-is.md)** para um percurso completo **ida e volta** desde `POST /core/v1/conversations` (SSE) até à chamada ao fornecedor LLM (OpenAI via adapter), com componentes, validações e diagrama de sequência. É o mapa mais direto para onboarding técnico neste tema.

## Documentação que complementa o `as-is`

O `as-is.md` é deliberadamente um **único fio narrativo**. Para aprofundar por tema, use estes marcos em `docs/`:

| Objetivo | Onde ir |
|----------|---------|
| SSE e conversação na perspetiva da API (headers, boundary, diagrama curto) | [Conversation — SSE and runtime](../Conversation/sse-and-runtime.md) |
| Execução do grafo, runtime, hooks e `ExecutionService` | [Execution](../Execution/index.md), em especial [execution-service](../Execution/execution-service.md), [runtime-executor](../Execution/graph-runtime/runtime-executor.md), [flow-lifecycle](../Execution/flow-lifecycle.md) |
| Camada LLM, executor e fornecedores | [LLM](../LLM/index.md), [llm-executor](../LLM/llm-executor.md), [providers-and-selection](../LLM/providers-and-selection.md) |
| MCP: registry, gateway e ferramentas HTTP | [MCP — registry and API](../MCP/registry-and-api.md), [gateway and runtime](../MCP/gateway-and-runtime.md), [MCP index](../MCP/index.md) |
| Tenants, auth e políticas | [Tenants](../Tenants/index.md), [Auth](../Auth/index.md), [Governance](../Governance/index.md) |
| Visão global do sistema | [Architecture overview](../Architecture/ARCHITECTURE.md), [Documentation map](../AI/documentation-map.md) |

Para setup operacional de tenant (checklist), ver também [Full tenant configuration](../Get-Started/full-tenant-configuration.md).

## Depois do “as-is”: transição para B2B SaaS

Quando o estado atual estiver claro, abra **[b2b-saas-tenant-experience.md](b2b-saas-tenant-experience.md)**. Esse documento não repete o fluxo conversação→LLM; assume o núcleo já descrito no `as-is` e foca-se na **evolução para uma experiência tipo SaaS B2B**: conta e billing, dashboard do tenant, chaves MCP estáveis, import OpenAPI→tools, outbound para APIs do cliente e fases de implementação (A/B/C).

Em termos de leitura: **as-is** = trincheiras de execução de hoje; **B2B SaaS** = produto-alvo, lacunas face ao estado atual e roteiro por fases.
