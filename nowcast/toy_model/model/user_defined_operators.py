import cvxpy


def absol(expression):
    """Element-wise absolute value (L1 building block)."""
    return cvxpy.abs(expression)
