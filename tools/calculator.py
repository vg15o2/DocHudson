"""
Calculator Tool — safe math evaluation.

LLMs hallucinate arithmetic. This tool doesn't.
Uses Python's ast module for safe expression parsing — no exec/eval.
"""

import ast
import math
import operator


# --- Tool Schema (what the LLM sees) ---

CALCULATOR_SCHEMA = {
    "name": "calculator",
    "description": (
        "Evaluate a mathematical expression. Use this for ANY arithmetic, "
        "unit conversions, percentages, or calculations. "
        "Supports: +, -, *, /, **, %, sqrt, sin, cos, tan, log, pi, e, abs, round. "
        "Examples: '2**10', 'sqrt(144)', 'sin(pi/4)', '15% of 200', '(3+4)*5'"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Math expression to evaluate, e.g. '(45 * 1.08) + 200'"
            },
        },
        "required": ["expression"],
    },
}


# --- Safe evaluator ---

# Allowed binary operations
_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

# Allowed unary operations
_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# Allowed functions and constants
_FUNCTIONS = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log2": math.log2,
    "log10": math.log10,
    "abs": abs,
    "round": round,
    "ceil": math.ceil,
    "floor": math.floor,
    "factorial": math.factorial,
}

_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
    "inf": math.inf,
}


def _safe_eval(node):
    """Recursively evaluate an AST node. Only allows math operations."""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)

    if isinstance(node, ast.Constant):  # numbers
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant type: {type(node.value).__name__}")

    if isinstance(node, ast.Name):  # pi, e, etc
        if node.id in _CONSTANTS:
            return _CONSTANTS[node.id]
        raise ValueError(f"Unknown variable: '{node.id}'")

    if isinstance(node, ast.BinOp):  # 3 + 4, 2 ** 10
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        op_type = type(node.op)
        if op_type in _BINOPS:
            return _BINOPS[op_type](left, right)
        raise ValueError(f"Unsupported operator: {op_type.__name__}")

    if isinstance(node, ast.UnaryOp):  # -5, +3
        operand = _safe_eval(node.operand)
        op_type = type(node.op)
        if op_type in _UNARYOPS:
            return _UNARYOPS[op_type](operand)
        raise ValueError(f"Unsupported unary operator: {op_type.__name__}")

    if isinstance(node, ast.Call):  # sqrt(4), log(100)
        if isinstance(node.func, ast.Name) and node.func.id in _FUNCTIONS:
            args = [_safe_eval(arg) for arg in node.args]
            return _FUNCTIONS[node.func.id](*args)
        func_name = getattr(node.func, "id", "unknown")
        raise ValueError(f"Unknown function: '{func_name}'")

    raise ValueError(f"Unsupported expression type: {type(node).__name__}")


# --- Tool Implementation ---

class CalculatorTool:
    """Safe math evaluator using AST parsing."""

    def calculate(self, expression: str) -> str:
        """Evaluate a math expression safely."""
        expr = expression.strip()

        if not expr:
            return "Error: empty expression"
        if len(expr) > 500:
            return "Error: expression too long (max 500 chars)"

        try:
            tree = ast.parse(expr, mode="eval")
            result = _safe_eval(tree)

            # Format nicely
            if isinstance(result, float):
                if result == int(result) and not math.isinf(result):
                    return f"{expr} = {int(result)}"
                return f"{expr} = {result:.10g}"
            return f"{expr} = {result}"

        except (ValueError, TypeError, SyntaxError, ZeroDivisionError) as e:
            return f"Error evaluating '{expr}': {e}"
