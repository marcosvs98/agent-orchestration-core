## Planning (3) — Estrutura do Projeto e Regras de Organização de Código

Objetivo deste planning: **garantir previsibilidade na evolução do código**, evitar acoplamento acidental e permitir que MCP Hosts naveguem, criem e modifiquem código sem violar o domínio.

Aqui definimos **onde cada coisa vive**, **por que vive ali** e **o que é proibido**.

---

### Princípio estrutural

A estrutura do projeto **reflete o domínio**, não o framework, não o runtime e não o canal.

Código é organizado por **responsabilidade**, não por tipo técnico genérico.

Controllers, services, schemas e ports existem **dentro de cada domínio**, nunca como pastas globais de negócio.

---

### Camadas globais (fora do domínio)

#### `adapters/`

Responsabilidade:
– Entradas e saídas do sistema
– HTTP, Webhook, Workers, Schedulers, Consumers

Regras:
– Adaptam payload para o core
– Nunca contêm lógica de negócio
– Nunca acessam diretamente outros adapters

Adapters chamam **controllers**, nunca services diretamente.

---

#### `infra/`

Responsabilidade:
– Implementações técnicas substituíveis

Inclui:
– database (ORM, migrations, repositories concretos)
– llm (providers de modelo)
– vector_store (backends vetoriais)
– cache (redis, memory, etc.)

Regras:
– Nunca importa código de domínio
– Implementa apenas interfaces definidas em `ports/`
– Pode ser trocado sem afetar domínio

Infra é detalhe. Sempre.

---

#### `ports/` (global)

Responsabilidade:
– Contratos técnicos transversais

Exemplos:
– AuthContext
– Clock
– Logger
– TransactionManager

Regras:
– Só interfaces
– Sem dependência de infra
– Usado por múltiplos domínios

---

### Estrutura interna de cada domínio (`packages/*`)

Todo domínio segue o mesmo padrão. Sem exceção.

#### `controllers/`

Responsabilidade:
– Orquestrar requests
– Validar input
– Chamar services

Regras:
– Não contém regra de negócio
– Não acessa infra diretamente
– Conhece schemas e services

Controllers são borda do domínio.

---

#### `services/`

Responsabilidade:
– Regra de negócio
– Coordenação de entidades
– Aplicação das invariantes

Regras:
– Não conhece HTTP, fila ou canal
– Não conhece ORM
– Fala com infra apenas via ports

Aqui está o **cérebro** do domínio.

---

#### `schemas/`

Responsabilidade:
– Contratos de dados
– DTOs
– Validação estrutural

Regras:
– Não contém lógica
– Não chama services
– Serve como fronteira de entrada e saída

Schemas estabilizam integração.

---

#### `ports/` (por domínio)

Responsabilidade:
– Contratos que o domínio precisa do mundo externo

Exemplos:
– Repository
– LLMClient
– VectorStoreClient

Regras:
– Apenas interfaces
– Implementadas em `infra/`
– Injetadas nos services

---

#### `exceptions/`

Responsabilidade:
– Erros semânticos do domínio

Regras:
– Não são erros técnicos
– Representam violações de regra
– Usadas pelos services

---

### Regras de dependência (invioláveis)

– Domain **nunca** depende de infra
– Infra **nunca** depende de domain
– Adapters **não** conversam entre si
– Services **não** conhecem controllers
– Controllers **não** contêm regra de negócio

Violou isso, violou a arquitetura.

---

### Organização de testes

Cada domínio testa **a si mesmo**.

– Testes de service são prioritários
– Infra é mockada via ports
– Adapter é testado por contrato

Não existe “teste global de sistema” sem intenção clara.

---

### O que é explicitamente proibido

– Lógica de negócio em controller
– Prompt hardcoded em adapter
– ORM dentro de service
– Chamada de tool dentro de agent
– IA decidindo efeito colateral

Esses são **anti-padrões estruturais**.
