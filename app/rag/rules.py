"""Small deterministic evaluator for formalized KB safety-rule triggers."""

from __future__ import annotations

from typing import Any


def evaluate_condition(condition: dict[str, Any], values: dict[str, Any]) -> bool:
    field = condition.get("field")
    if not field or field not in values:
        return False
    actual = values[field]
    expected = condition.get("value")
    op = condition.get("op")
    if op == "eq":
        return actual == expected
    if op == "neq":
        return actual != expected
    if op == "gt":
        return actual > expected
    if op == "gte":
        return actual >= expected
    if op == "lt":
        return actual < expected
    if op == "in":
        return actual in expected
    raise ValueError(f"Unsupported safety-rule operator: {op}")


def evaluate_trigger(trigger: dict[str, Any], values: dict[str, Any]) -> bool:
    groups = trigger.get("groups") or []
    if not groups:
        return False
    evaluated = [
        all(evaluate_condition(condition, values) for condition in group)
        for group in groups
    ]
    return any(evaluated) if trigger.get("logic") == "or" else all(evaluated)


def validate_rule_tests(rule: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    trigger = rule.get("trigger") or {}
    for kind in ("positive_tests", "negative_tests"):
        for test in rule.get(kind) or []:
            actual = evaluate_trigger(trigger, test.get("input") or {})
            expected = bool(test.get("expected"))
            if actual != expected:
                failures.append(f"{rule.get('id')}:{test.get('name')}: expected {expected}, got {actual}")
    return failures
