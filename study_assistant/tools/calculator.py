"""A deliberately small, safe arithmetic tool."""

import ast


def _evaluate(node: ast.AST):
    if isinstance(node, ast.Expression): return _evaluate(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)): return node.value
    if isinstance(node, ast.BinOp):
        left, right = _evaluate(node.left), _evaluate(node.right)
        operations = {ast.Add: lambda: left + right, ast.Sub: lambda: left - right, ast.Mult: lambda: left * right, ast.Div: lambda: left / right}
        if type(node.op) in operations: return operations[type(node.op)]()
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _evaluate(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    raise ValueError("Use numbers, parentheses, +, -, *, and / only.")


def calculator(expression: str) -> dict:
    """Calculate a short arithmetic expression safely."""
    try:
        return {"expression": expression, "result": _evaluate(ast.parse(expression, mode="eval"))}
    except (SyntaxError, TypeError, ValueError, ZeroDivisionError) as error:
        return {"error": str(error)}
