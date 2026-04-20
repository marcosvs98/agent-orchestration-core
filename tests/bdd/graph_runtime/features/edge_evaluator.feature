# language: en
Feature: Edge condition evaluation
  Boolean edge conditions compile to serializable ASTs and evaluate against runtime context.

  Scenario: Simple equality evaluates against context
    Given the edge condition checks string equality on status
    When we evaluate on matching status context
    Then the result is true

  Scenario: Custom HasAny helper matches list semantics
    Given the edge condition uses HasAny on tag lists
    When we evaluate on overlapping tags context
    Then the result is true

  Scenario: Invalid syntax fails at compile time
    When compiling the invalid edge condition "((("
    Then compile fails with domain validation

  Scenario: Collect identifiers finds root paths
    Given a compiled condition from "foo.bar == 1"
    When identifiers are collected from the compiled tree
    Then "foo" is among the collected identifiers
