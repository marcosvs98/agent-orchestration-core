### Data-first audit trail

Events carry correlation_id, causation_id, schema_version, and payload; audit answers rely on persisted data (channel metadata included) instead of logs.

### Event sample

```json
[
  {
    "causation_id": null,
    "correlation_id": "a257e521-23db-43ab-b823-c328c03c955b",
    "event_sequence": 1,
    "payload": {
      "channel": "http"
    },
    "type": "FlowStarted"
  },
  {
    "causation_id": "79018c1b-d4f9-439d-bc4d-46630cd2effd",
    "correlation_id": "a257e521-23db-43ab-b823-c328c03c955b",
    "event_sequence": 2,
    "payload": {
      "result": "ok"
    },
    "type": "FlowCompleted"
  }
]
```
