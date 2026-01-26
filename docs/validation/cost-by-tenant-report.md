### Billing summary

Costs are summed per tenant using distinct agent_run_id values to avoid replay duplication.

### Totals by tenant

```json
{
  "00000000-0000-0000-0000-000000000001": 1.5
}
```

### Agent run rows

```json
[
  {
    "agent_run_id": "1a2dd628-b999-4b7a-901b-5b8da0416026",
    "billing_policy_version_id": "00000000-0000-0000-0000-000000000101",
    "estimated_cost": 1.0,
    "tenant_id": "00000000-0000-0000-0000-000000000001"
  },
  {
    "agent_run_id": "d079cfb3-27c3-4e03-b512-9cf536ceed11",
    "billing_policy_version_id": "00000000-0000-0000-0000-000000000101",
    "estimated_cost": 0.5,
    "tenant_id": "00000000-0000-0000-0000-000000000001"
  }
]
```
