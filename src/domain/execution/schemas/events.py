from enum import StrEnum


class ExecutionEventType(StrEnum):
    FlowStarted = "FlowStarted"
    FlowRunning = "FlowRunning"
    FlowWaiting = "FlowWaiting"
    FlowCompleted = "FlowCompleted"
    FlowFailed = "FlowFailed"
    FlowEscalated = "FlowEscalated"

    NodeEntered = "NodeEntered"
    NodeStarted = "NodeStarted"
    NodeSkipped = "NodeSkipped"
    NodeCompleted = "NodeCompleted"
    NodeFailed = "NodeFailed"
    EdgeEvaluated = "EdgeEvaluated"

    AgentRunStarted = "AgentRunStarted"
    AgentRunCompleted = "AgentRunCompleted"
    AgentRunFailed = "AgentRunFailed"
    AgentRunRetried = "AgentRunRetried"
    AgentRunAborted = "AgentRunAborted"

    ToolInvocationRequested = "ToolInvocationRequested"
    ToolInvocationSucceeded = "ToolInvocationSucceeded"
    ToolInvocationFailed = "ToolInvocationFailed"
    ToolInvocationTimedOut = "ToolInvocationTimedOut"
    ToolInvocationRetried = "ToolInvocationRetried"
    LLMCallStarted = "LLMCallStarted"
    LLMCallCompleted = "LLMCallCompleted"
    LLMCallFailed = "LLMCallFailed"
    GuardrailChecked = "GuardrailChecked"
    GuardrailBlocked = "GuardrailBlocked"
    GuardrailDegraded = "GuardrailDegraded"

    PolicyEvaluated = "PolicyEvaluated"
    PolicyDenied = "PolicyDenied"
    PolicyViolated = "PolicyViolated"
    EscalationTriggered = "EscalationTriggered"
    ManualInterventionRequested = "ManualInterventionRequested"

    AuthFailed = "AuthFailed"
    LimitExceeded = "LimitExceeded"
    BillingPolicyViolated = "BillingPolicyViolated"
    ValidationFailed = "ValidationFailed"
    SecretAccessed = "SecretAccessed"
    NodePromptUpdated = "NodePromptUpdated"
    NodePromptExecuted = "NodePromptExecuted"
