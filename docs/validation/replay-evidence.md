### Determinism

Two FlowRuns created from the same payload and correlation_id produced identical event topology.

### FlowRun A events

```json
[
  {
    "correlation_id": "c795c468-1769-4671-a4d6-e6f27da7718e",
    "event_sequence": 1,
    "payload": {
      "payload": {
        "text": "hello"
      }
    },
    "type": "FlowStarted"
  },
  {
    "correlation_id": "c795c468-1769-4671-a4d6-e6f27da7718e",
    "event_sequence": 2,
    "payload": {
      "result": "ok"
    },
    "type": "FlowCompleted"
  }
]
```

### FlowRun B events

```json
[
  {
    "correlation_id": "c795c468-1769-4671-a4d6-e6f27da7718e",
    "event_sequence": 1,
    "payload": {
      "payload": {
        "text": "hello"
      }
    },
    "type": "FlowStarted"
  },
  {
    "correlation_id": "c795c468-1769-4671-a4d6-e6f27da7718e",
    "event_sequence": 2,
    "payload": {
      "result": "ok"
    },
    "type": "FlowCompleted"
  }
]
```