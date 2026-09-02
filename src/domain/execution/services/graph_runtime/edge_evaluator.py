from __future__ import annotations

from typing import Any, Dict

import pyparsing

from exceptions.service_exceptions import DomainValidationException


PATCH_DELIMITER = "."

IDENTIFIER = pyparsing.Word(pyparsing.alphas, pyparsing.alphanums + "_")

LBRACK = pyparsing.Suppress("[")
RBRACK = pyparsing.Suppress("]")

INDEX = pyparsing.Word(pyparsing.nums).set_parse_action(lambda t: int(t[0]))

PATH_SEGMENT = pyparsing.Group(IDENTIFIER + pyparsing.ZeroOrMore(LBRACK + INDEX + RBRACK))

PROPERTY_PATH = pyparsing.DelimitedList(
    PATH_SEGMENT,
    delim=PATCH_DELIMITER,
).set_parse_action(lambda t: SubstituteVal(t.as_list()))

AND_OPERATOR = pyparsing.CaselessKeyword("and")
OR_OPERATOR = pyparsing.CaselessKeyword("or")
NOT_OPERATOR = pyparsing.CaselessKeyword("not")

LEFT_PARENTHESIS = pyparsing.Suppress("(")
RIGHT_PARENTHESIS = pyparsing.Suppress(")")

BINARY_OPERATORS = pyparsing.one_of(
    "= == != < > >= <= eq ne lt le gt ge in notin is isnot ≠ ≤ ≥ ∈ ∉ ⊆ ⊇ ∩ not∩",
    caseless=True,
)

E = pyparsing.CaselessLiteral("E")
NUMBER_SIGN = pyparsing.Word("+-", exact=1)

REAL_NUMBER = pyparsing.Combine(
    pyparsing.Optional(NUMBER_SIGN)
    + (
        pyparsing.Word(pyparsing.nums) + "." + pyparsing.Optional(pyparsing.Word(pyparsing.nums))
        | ("." + pyparsing.Word(pyparsing.nums))
    )
    + pyparsing.Optional(E + pyparsing.Optional(NUMBER_SIGN) + pyparsing.Word(pyparsing.nums))
).set_parse_action(lambda t: float(t[0]))

INTEGER = pyparsing.Combine(
    pyparsing.Optional(NUMBER_SIGN)
    + pyparsing.Word(pyparsing.nums)
    + pyparsing.Optional(E + pyparsing.Optional("+") + pyparsing.Word(pyparsing.nums))
).set_parse_action(lambda t: int(t[0]))

STRING = pyparsing.quoted_string.add_parse_action(pyparsing.remove_quotes)

BOOLEAN = pyparsing.one_of(
    "True False",
    caseless=True,
).set_parse_action(lambda t: t[0].lower() == "true")

NONE = pyparsing.CaselessLiteral("none").set_parse_action(lambda _: None)


class SubstituteVal:
    def __init__(self, tokens):
        self._segments = tokens

    @property
    def segments(self) -> list[list[Any]]:
        return self._segments

    def resolve(self, context: Any) -> Any:
        if context is None:
            raise DomainValidationException(message="edge_evaluation_error")

        val = context

        for segment in self._segments:
            name = segment[0]

            if isinstance(val, dict):
                if name not in val:
                    raise DomainValidationException(message="edge_evaluation_error")
                val = val[name]
            elif isinstance(val, (list, tuple)):
                try:
                    val = [
                        item[name]
                        if isinstance(item, dict) and name in item
                        else getattr(item, name)
                        if hasattr(item, name)
                        else None
                        for item in val
                    ]
                except (KeyError, AttributeError, TypeError) as exc:
                    raise DomainValidationException(message="edge_evaluation_error") from exc
            elif hasattr(val, name):
                val = getattr(val, name)
            else:
                raise DomainValidationException(message="edge_evaluation_error")

            for idx in segment[1:]:
                if not isinstance(val, (list, tuple)):
                    raise DomainValidationException(message="edge_evaluation_error")
                try:
                    val = val[idx]
                except (IndexError, TypeError) as exc:
                    raise DomainValidationException(message="edge_evaluation_error") from exc

        return val


class LenVal:
    def __init__(self, value: Any):
        self._value = value

    @property
    def value(self) -> Any:
        return self._value

    def resolve(self, context: Any) -> int:
        base_value = (
            self._value.resolve(context) if isinstance(self._value, SubstituteVal) else self._value
        )
        try:
            return len(base_value)
        except Exception as exc:
            raise DomainValidationException(message="edge_evaluation_error") from exc


LEN = pyparsing.CaselessKeyword("len")
LEN_VALUE = (
    LEN + pyparsing.Suppress("(") + PROPERTY_PATH + pyparsing.Suppress(")")
).set_parse_action(lambda t: LenVal(t[1]))

EXPR = pyparsing.Forward()

LIST_ITEM = STRING | REAL_NUMBER | INTEGER | BOOLEAN | NONE | PROPERTY_PATH
LIST_LITERAL = (
    LBRACK + pyparsing.Optional(pyparsing.Group(pyparsing.delimitedList(LIST_ITEM))) + RBRACK
).set_parse_action(lambda t: {"__type__": "list", "values": list(t[0]) if t else []})

FUNC_CALL = (
    IDENTIFIER
    + LEFT_PARENTHESIS
    + pyparsing.Group(pyparsing.delimitedList(EXPR))
    + RIGHT_PARENTHESIS
).set_parse_action(lambda t: [t[0]] + list(t[1]))

SIMPLE_VALUES = (
    REAL_NUMBER
    | INTEGER
    | STRING
    | BOOLEAN
    | NONE
    | LEN_VALUE
    | LIST_LITERAL
    | pyparsing.Group(FUNC_CALL)
    | PROPERTY_PATH
    | (LEFT_PARENTHESIS + EXPR + RIGHT_PARENTHESIS)
)

EXPR << pyparsing.infix_notation(  # pylint: disable=expression-not-assigned
    SIMPLE_VALUES,
    [
        (BINARY_OPERATORS, 2, pyparsing.opAssoc.LEFT),
        (NOT_OPERATOR, 1, pyparsing.opAssoc.RIGHT),
        (AND_OPERATOR, 2, pyparsing.opAssoc.LEFT),
        (OR_OPERATOR, 2, pyparsing.opAssoc.LEFT),
    ],
)

BOOLEAN_EXPRESSION = EXPR

COMPARISON_OPERATORS = {
    "=": lambda x, y: x == y,
    "==": lambda x, y: x == y,
    "eq": lambda x, y: x == y,
    "!=": lambda x, y: x != y,
    "ne": lambda x, y: x != y,
    "≠": lambda x, y: x != y,
    ">": lambda x, y: x > y,
    "gt": lambda x, y: x > y,
    ">=": lambda x, y: x >= y,
    "ge": lambda x, y: x >= y,
    "≥": lambda x, y: x >= y,
    "<": lambda x, y: x < y,
    "lt": lambda x, y: x < y,
    "<=": lambda x, y: x <= y,
    "le": lambda x, y: x <= y,
    "≤": lambda x, y: x <= y,
    "in": lambda x, y: x in y,
    "∈": lambda x, y: x in y,
    "notin": lambda x, y: x not in y,
    "∉": lambda x, y: x not in y,
    "is": lambda x, y: x is y,
    "isnot": lambda x, y: x is not y,
}

SET_OPERATORS = {
    "⊆": lambda x, y: all(xi in y for xi in x),
    "⊇": lambda x, y: all(yi in x for yi in y),
    "∩": lambda x, y: any(xi in y for xi in x),
    "not∩": lambda x, y: not any(xi in y for xi in x),
}

COMPARISON_AND_SET_OPERATORS = {
    **COMPARISON_OPERATORS,
    **SET_OPERATORS,
}

CUSTOM_FUNCTIONS = {
    "HasAny": lambda lst, vals: any(x in vals for x in lst),
    "HasAll": lambda lst, vals: all(x in vals for x in lst),
    "AnyEquals": lambda lst, value: any(x == value for x in lst),
    "AllEquals": lambda lst, value: all(x == value for x in lst),
    "AnyNonEmpty": lambda lst: any(bool(item) for item in lst),
    "AllNonEmpty": lambda lst: (
        isinstance(lst, (list, tuple)) and len(lst) > 0 and all(bool(item) for item in lst)
    ),
}


class EdgeEvaluator:
    @staticmethod
    def compile_condition(condition: str) -> Any:
        try:
            parsed = BOOLEAN_EXPRESSION.parse_string(
                condition,
                parse_all=True,
            )
            return EdgeEvaluator._to_serializable(parsed[0])
        except Exception as exc:
            raise DomainValidationException(
                message="edge_condition_invalid",
                input_data={"condition": condition},
                errors=[
                    {
                        "error": "condition_compile_failed",
                        "exception_type": type(exc).__name__,
                        "exception_message": str(exc),
                    }
                ],
            ) from exc

    @staticmethod
    def collect_identifiers(compiled_condition: Any) -> list[str]:
        identifiers: list[str] = []

        def visit(node: Any) -> None:
            if isinstance(node, dict):
                if node.get("__type__") == "path":
                    segments = node.get("segments", [])
                    if segments and isinstance(segments[0], list) and segments[0]:
                        root = segments[0][0]
                        if isinstance(root, str):
                            identifiers.append(root)
                else:
                    for value in node.values():
                        visit(value)
                return
            if isinstance(node, list):
                for value in node:
                    visit(value)

        visit(compiled_condition)
        return identifiers

    @staticmethod
    def is_true(
        condition: str,
        context: Dict[str, Any],
        compiled_condition: Any | None = None,
    ) -> bool:
        try:
            expression = (
                compiled_condition
                if compiled_condition is not None
                else EdgeEvaluator.compile_condition(condition)
            )
            result = EdgeEvaluator._eval(expression, context)

            if not isinstance(result, bool):
                raise DomainValidationException(
                    message="edge_evaluation_error",
                    input_data={
                        "condition": condition,
                        "expression": expression,
                        "compiled_condition": compiled_condition,
                        "context": context,
                    },
                    errors=[
                        {
                            "error": "result_not_boolean",
                            "evaluated_result": result,
                        }
                    ],
                )

            return result

        except DomainValidationException as exc:
            exc.input_data = {
                "condition": condition,
                "context": context,
            }
            if hasattr(exc, "_errors") and exc._errors is not None:
                exc._errors.append(
                    {
                        "error": "edge_evaluation_failed",
                        "condition": condition,
                        "compiled_condition": compiled_condition,
                    }
                )
            raise

        except Exception as exc:
            raise DomainValidationException(
                message="edge_evaluation_error",
                input_data={
                    "condition": condition,
                    "compiled_condition": compiled_condition,
                    "context": context,
                },
                errors=[
                    {
                        "error": "unexpected_exception",
                        "exception_type": type(exc).__name__,
                        "exception_message": str(exc),
                    }
                ],
            ) from exc

    @staticmethod
    def _eval(node: Any, context: Dict[str, Any]) -> Any:
        if isinstance(node, dict):
            if node.get("__type__") == "path":
                return SubstituteVal(node.get("segments", [])).resolve(context)
            if node.get("__type__") == "len":
                value = node.get("value")
                if isinstance(value, dict) and value.get("__type__") == "path":
                    path_value = SubstituteVal(value.get("segments", []))
                    return LenVal(path_value).resolve(context)
                return LenVal(value).resolve(context)
            if node.get("__type__") == "list":
                return [EdgeEvaluator._eval(v, context) for v in node.get("values", [])]
            raise DomainValidationException(message="edge_evaluation_error")

        if isinstance(node, pyparsing.ParseResults):
            return EdgeEvaluator._eval(node.as_list(), context)

        if isinstance(node, list):
            if len(node) > 0 and isinstance(node[0], str) and node[0] in CUSTOM_FUNCTIONS:
                func_name = node[0]
                args = [EdgeEvaluator._eval(arg, context) for arg in node[1:]]
                return CUSTOM_FUNCTIONS[func_name](*args)
            if len(node) == 2 and isinstance(node[0], str) and node[0].lower() == "not":
                return not bool(EdgeEvaluator._eval(node[1], context))
            if len(node) == 3:
                left = EdgeEvaluator._eval(node[0], context)
                operator = node[1].lower()
                right = EdgeEvaluator._eval(node[2], context)

                if operator in COMPARISON_AND_SET_OPERATORS:
                    try:
                        return COMPARISON_AND_SET_OPERATORS[operator](left, right)
                    except TypeError as exc:
                        raise DomainValidationException(
                            message="edge_evaluation_error",
                            input_data={
                                "operator": operator,
                                "left": left,
                                "right": right,
                            },
                            errors=[
                                {
                                    "error": "type_error_on_comparison",
                                    "operator": operator,
                                }
                            ],
                        ) from exc

                if operator == "and":
                    return bool(left) and bool(right)

                if operator == "or":
                    return bool(left) or bool(right)

                raise DomainValidationException(
                    message="edge_condition_not_supported",
                    input_data={
                        "operator": operator,
                    },
                    errors=[
                        {
                            "error": "unsupported_operator",
                            "operator": operator,
                        }
                    ],
                )

            result = EdgeEvaluator._eval(node[0], context)
            i = 1
            while i < len(node):
                op = node[i].lower()
                right = EdgeEvaluator._eval(node[i + 1], context)

                if op == "and":
                    result = bool(result) and bool(right)
                elif op == "or":
                    result = bool(result) or bool(right)
                else:
                    raise DomainValidationException(
                        message="edge_condition_not_supported",
                        input_data={
                            "operator": op,
                        },
                        errors=[
                            {
                                "error": "unsupported_operator",
                                "operator": op,
                            }
                        ],
                    )
                i += 2
            return result

        if isinstance(node, SubstituteVal):
            try:
                return node.resolve(context)
            except DomainValidationException:
                raise
            except Exception as exc:
                raise DomainValidationException(
                    message="edge_evaluation_error",
                    input_data={
                        "context": context,
                    },
                    errors=[
                        {
                            "error": "variable_resolution_failed",
                        }
                    ],
                ) from exc

        if isinstance(node, LenVal):
            try:
                return node.resolve(context)
            except Exception as exc:
                raise DomainValidationException(
                    message="edge_evaluation_error",
                    input_data={
                        "context": context,
                    },
                    errors=[
                        {
                            "error": "len_resolution_failed",
                        }
                    ],
                ) from exc

        return node

    @staticmethod
    def _to_serializable(node: Any) -> Any:
        if isinstance(node, pyparsing.ParseResults):
            return EdgeEvaluator._to_serializable(node.as_list())
        if isinstance(node, SubstituteVal):
            return {"__type__": "path", "segments": node.segments}
        if isinstance(node, LenVal):
            return {
                "__type__": "len",
                "value": EdgeEvaluator._to_serializable(node.value),
            }
        if isinstance(node, dict) and node.get("__type__") == "list":
            return {
                "__type__": "list",
                "values": [EdgeEvaluator._to_serializable(v) for v in node.get("values", [])],
            }
        if isinstance(node, list):
            return [EdgeEvaluator._to_serializable(item) for item in node]
        return node
