# language: en
Feature: Graph compiler
  The compiler turns a validated flow snapshot into an ExecutionPlan with adjacency and terminals.

  Background:
    Given a runtime tracer stub

  Scenario: Valid linear graph compiles to a plan
    Given a linear two-node snapshot with compiled edges
    When the graph compiler compiles the snapshot
    Then the plan start node is "n1"
    And the plan lists "n2" as a terminal node
    And the structural hash is stored on the plan

  Scenario: Missing start node is rejected
    Given a snapshot whose start_node is not in nodes
    When the graph compiler compiles the snapshot expecting failure
    Then validation fails with message "start_node_not_found"

  Scenario: Empty edges are rejected
    Given a snapshot with nodes but no edges
    When the graph compiler compiles the snapshot expecting failure
    Then validation fails with message "edges_required"

  Scenario: Missing terminal nodes is rejected
    Given a snapshot with only non-terminal node types
    When the graph compiler compiles the snapshot expecting failure
    Then validation fails with message "no_terminal_nodes"

  Scenario: Edge without compiled condition is rejected
    Given a snapshot with an edge missing compiled_condition
    When the graph compiler compiles the snapshot expecting failure
    Then validation fails with message "compiled_condition_missing"

  Scenario: Unreachable nodes are rejected
    Given a snapshot with an isolated unreachable node
    When the graph compiler compiles the snapshot expecting failure
    Then validation fails with message "unreachable_nodes"

  Scenario: Undocumented cycle without LOOP edge kind is rejected
    Given a two-node cycle using only NORMAL edges
    When the graph compiler compiles the snapshot expecting failure
    Then validation fails with message "cycle_not_marked_loop"

  Scenario: Cycle is allowed when a back-edge is marked LOOP
    Given a two-node cycle with the back-edge marked LOOP
    When the graph compiler compiles the snapshot
    Then the plan start node is "n1"
