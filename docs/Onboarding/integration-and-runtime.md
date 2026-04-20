# Onboarding — integration and runtime

**Onboarding** tracks program definitions and runs **alongside** the main flow execution product; it uses its own service and HTTP surface under `domain/onboarding/`.

## Placement

```mermaid
flowchart LR
  subgraph ob["domain/onboarding"]
    C[OnboardingController]
    S[OnboardingService]
  end
  subgraph exec["Execution"]
    SR[step_run / node runs]
  end
  S --> SR
```

- Step-level execution details align with tables in [Persistence tables](../Glossary/persistence-tables.md) (`step_run` under **Runtime execution**).

## Related

- [HTTP API](http-api.md)
- [Execution](../Execution/index.md)
