import sympy as sp


def not_allowed(*args, **kwargs):
    raise RuntimeError("Calling sympy.series is not allowed in this question. You can still use sympy to compute derivatives")


sp.series = not_allowed
