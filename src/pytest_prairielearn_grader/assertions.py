"""Student-friendly assertion helpers for the PrairieLearn autograder.

These functions produce clean, readable failure messages designed for students
who may not be comfortable reading Python tracebacks.  Combine these with
``@pytest.mark.output(level="friendly")`` to suppress all traceback noise and
show *only* the human-readable message.

Typical usage::

    from pytest_prairielearn_grader.assertions import assert_equal, assert_fn_equal

    @pytest.mark.output(level="friendly")
    @pytest.mark.grading_data(name="Test addition", points=5)
    def test_add(sandbox):
        assert_fn_equal(sandbox, "add", args=(2, 3), expected=5)
"""

from __future__ import annotations

import os
from typing import Any

from .fixture import _SandboxBase
from .utils import format_call
from .utils import format_value


def _build_failure_lines(
    *,
    expected: Any,
    actual: Any,
    description: str | None = None,
    msg: str | None = None,
) -> str:
    """Build the multi-line student-facing failure message."""
    lines: list[str] = []
    if description:
        lines.append(f"Checking: {description}")
    lines.append(f"Expected output: {format_value(expected)}")
    lines.append(f"Your code output: {format_value(actual)}")
    if msg:
        lines.append(msg)
    else:
        lines.append("The expected and actual output do not match.")
    return os.linesep.join(lines)


# ---------------------------------------------------------------------------
# Standalone assertions (work with any pre-computed values)
# ---------------------------------------------------------------------------


def assert_equal(
    actual: Any,
    expected: Any,
    *,
    msg: str | None = None,
    description: str | None = None,
) -> None:
    """Assert ``actual == expected`` with a student-friendly failure message.

    Parameters
    ----------
    actual:
        The value produced by student code.
    expected:
        The correct / reference value.
    msg:
        Optional custom message appended on failure.  When *None* a default
        "The expected and actual output do not match." message is used.
    description:
        Optional label like ``"add(2, 3)"`` shown as the *Checking:* line.

    Raises
    ------
    AssertionError
        With a clean, multi-line message when the values differ.
    """
    if actual == expected:
        return
    raise AssertionError(_build_failure_lines(expected=expected, actual=actual, description=description, msg=msg))


def assert_approx_equal(
    actual: Any,
    expected: Any,
    *,
    rtol: float = 1e-5,
    atol: float = 1e-8,
    msg: str | None = None,
    description: str | None = None,
) -> None:
    """Assert two numeric values are approximately equal.

    Uses the formula ``|actual - expected| <= atol + rtol * |expected|``.

    Parameters
    ----------
    actual:
        The numeric value produced by student code.
    expected:
        The correct / reference numeric value.
    rtol:
        Relative tolerance (default ``1e-5``).
    atol:
        Absolute tolerance (default ``1e-8``).
    msg:
        Optional custom failure message.
    description:
        Optional label for the *Checking:* line.

    Raises
    ------
    AssertionError
        When the values are not within tolerance.
    """
    try:
        diff = abs(actual - expected)
        within_tolerance = diff <= atol + rtol * abs(expected)
    except TypeError:
        within_tolerance = False

    if within_tolerance:
        return

    default_msg = f"The values are not close enough (rtol={rtol}, atol={atol})."
    raise AssertionError(
        _build_failure_lines(
            expected=expected,
            actual=actual,
            description=description,
            msg=msg or default_msg,
        )
    )


def assert_true(
    condition: Any,
    *,
    msg: str | None = None,
) -> None:
    """Assert that *condition* is truthy with a student-friendly message.

    Parameters
    ----------
    condition:
        Any value; the assertion passes when ``bool(condition)`` is ``True``.
    msg:
        Custom failure message.  Defaults to
        ``"Expected the condition to be true, but it was false."``.
    """
    if condition:
        return
    raise AssertionError(msg or "Expected the condition to be true, but it was false.")


def assert_false(
    condition: Any,
    *,
    msg: str | None = None,
) -> None:
    """Assert that *condition* is falsy with a student-friendly message.

    Parameters
    ----------
    condition:
        Any value; the assertion passes when ``bool(condition)`` is ``False``.
    msg:
        Custom failure message.  Defaults to
        ``"Expected the condition to be false, but it was true."``.
    """
    if not condition:
        return
    raise AssertionError(msg or "Expected the condition to be false, but it was true.")


def assert_plot_equal(
    plot: Any,
    expected: Any,
    *,
    name: str = "your plot",
    rtol: float = 1e-5,
    atol: float = 1e-8,
    check_scales: bool = True,
    check_data: bool = True,
    ordered: bool = False,
    allow_extra: bool = False,
    check_labels: bool = False,
    check_titles: bool = False,
    check_legend: bool = False,
    check_limits: bool = False,
    check_styles: bool = False,
    check_texts: bool = False,
    msg: str | None = None,
) -> None:
    """Assert that a student's matplotlib plot matches a reference plot.

    Both plots can be a ``Figure`` or an ``Axes``.  ``sandbox.query`` returns
    a student's plot as a ``Figure``; the reference is usually drawn by the
    test itself.  Subplots are compared in order.

    By default this checks the number of subplots, the axis scales, and the
    data in each line, ``axhline`` and ``axvline`` line, scatter plot and bar
    plot, which must have the same number of each kind.  Series can be in any order, and a line also matches
    when its points are in reverse order.  Scatter points and bars can be in
    any order.  Numbers are compared with ``numpy.allclose``.

    Parameters
    ----------
    plot:
        The student's plot.  Anything other than a ``Figure`` or ``Axes``
        fails the assertion.
    expected:
        The reference plot.
    name:
        What to call the student's plot in failure messages.
    rtol, atol:
        Tolerances for comparing data and axis limits.
    check_scales:
        Compare the x and y axis scales, such as ``"linear"`` and ``"log"``.
    check_data:
        Compare the data in lines, scatter plots and bar plots.
    ordered:
        Require lines, scatter plots, bar plots and legend labels to be in
        the same order as in the reference.
    allow_extra:
        Allow the student's plot to have more lines, scatter plots, bar
        plots, text or annotations than the reference.
    check_labels:
        Compare the x and y axis labels exactly.
    check_titles:
        Compare the titles of each subplot and the figure exactly.
    check_legend:
        Compare the legend's labels and title, or that neither plot has a
        legend.
    check_limits:
        Compare the x and y axis limits.
    check_styles:
        Compare line colors, line styles and markers, scatter point colors,
        and bar colors and orientation.
    check_texts:
        Compare the strings of ``text`` and ``annotate`` labels, and the point
        each annotation points at.  The position of plain text isn't compared.
        Extra text is allowed with *allow_extra*.
    msg:
        Optional message to show instead of the description of the
        difference.

    Raises
    ------
    AssertionError
        Describing the first difference found.
    TypeError
        When *expected* is not a ``Figure`` or ``Axes``.
    """
    # matplotlib is an optional dependency, so only import it when a plot is checked.
    from .plot_checks import plot_mismatch  # noqa: PLC0415

    mismatch = plot_mismatch(
        plot,
        expected,
        name=name,
        rtol=rtol,
        atol=atol,
        check_scales=check_scales,
        check_data=check_data,
        ordered=ordered,
        allow_extra=allow_extra,
        check_labels=check_labels,
        check_titles=check_titles,
        check_legend=check_legend,
        check_limits=check_limits,
        check_styles=check_styles,
        check_texts=check_texts,
    )
    if mismatch is not None:
        raise AssertionError(msg or mismatch)


# ---------------------------------------------------------------------------
# Sandbox-integrated assertions (call student function + compare result)
# ---------------------------------------------------------------------------


def assert_fn_equal(
    sandbox: _SandboxBase,
    func_name: str,
    *,
    args: tuple[Any, ...] = (),
    kwargs: dict[str, Any] | None = None,
    expected: Any,
    msg: str | None = None,
    description: str | None = None,
    query_timeout: float = 1.0,
) -> Any:
    """Call a student function and assert its return value equals *expected*.

    This is a convenience wrapper that combines
    ``sandbox.query_function(...)`` with :func:`assert_equal` and
    automatically produces a message like::

        Checking: add(2, 3)
        Expected output: 5
        Your code output: 4
        The expected and actual output do not match.

    Parameters
    ----------
    sandbox:
        The sandbox fixture (``StudentFixture`` or ``WorkspaceFixture``).
    func_name:
        Name of the function to call in the student sandbox.
    args:
        Positional arguments forwarded to the student function.
    kwargs:
        Keyword arguments forwarded to the student function.
    expected:
        The correct / reference return value.
    msg:
        Optional custom failure message.
    description:
        Optional label for the ``Checking:`` line. Defaults to the function call.
    query_timeout:
        Timeout in seconds for the function call (default ``1.0``).

    Returns
    -------
    The return value from the student function (useful for further checks).

    Raises
    ------
    AssertionError
        When the return value does not equal *expected*.
    RuntimeError / TimeoutError / NameError
        Propagated from ``sandbox.query_function`` on execution errors.
    """
    call_kwargs = kwargs or {}
    actual = sandbox.query_function(func_name, *args, query_timeout=query_timeout, **call_kwargs)
    call_description = description or format_call(func_name, args, kwargs)
    assert_equal(actual, expected, msg=msg, description=call_description)
    return actual


def assert_fn_approx_equal(
    sandbox: _SandboxBase,
    func_name: str,
    *,
    args: tuple[Any, ...] = (),
    kwargs: dict[str, Any] | None = None,
    expected: Any,
    rtol: float = 1e-5,
    atol: float = 1e-8,
    msg: str | None = None,
    description: str | None = None,
    query_timeout: float = 1.0,
) -> Any:
    """Call a student function and assert its return value is approximately
    equal to *expected*.

    Behaves like :func:`assert_fn_equal` but uses :func:`assert_approx_equal`
    for the comparison.

    Returns
    -------
    The return value from the student function.
    """
    call_kwargs = kwargs or {}
    actual = sandbox.query_function(func_name, *args, query_timeout=query_timeout, **call_kwargs)
    call_description = description or format_call(func_name, args, kwargs)
    assert_approx_equal(actual, expected, rtol=rtol, atol=atol, msg=msg, description=call_description)
    return actual


# ---------------------------------------------------------------------------
# PyTorch tensor assertions
# ---------------------------------------------------------------------------


def _as_cpu_tensor(value: Any) -> Any:
    """Coerce a value to a detached CPU tensor so comparisons never touch autograd or a device."""
    import torch  # noqa: PLC0415

    return torch.as_tensor(value).detach().cpu()


def _tensor_detail(value: Any) -> str:
    """A short, student-readable description of a tensor's shape, dtype and (if small) values."""
    tensor = _as_cpu_tensor(value)
    dtype = str(tensor.dtype).removeprefix("torch.")
    detail = f"a tensor with shape {tuple(tensor.shape)} and dtype {dtype}"
    if tensor.numel() <= 12:
        detail += f" and values {tensor.tolist()}"
    return detail


def assert_tensor_allclose(
    actual: Any,
    expected: Any,
    *,
    rtol: float = 1e-5,
    atol: float = 1e-8,
    check_dtype: bool = False,
    equal_nan: bool = True,
    msg: str | None = None,
    description: str | None = None,
) -> None:
    """Assert two PyTorch tensors are equal within a tolerance.

    Uses the formula ``|actual - expected| <= atol + rtol * |expected|`` elementwise.
    ``actual`` and ``expected`` may be anything ``torch.as_tensor`` accepts (a tensor,
    a NumPy array, or a nested list). Tensors are detached and moved to the CPU before
    comparison, so gradients and device placement don't matter.

    Parameters
    ----------
    actual:
        The tensor produced by student code.
    expected:
        The correct / reference tensor.
    rtol:
        Relative tolerance (default ``1e-5``).
    atol:
        Absolute tolerance (default ``1e-8``).
    check_dtype:
        When True, the two tensors must also share a dtype. When False (default), an
        integer tensor and the equivalent float tensor compare equal.
    equal_nan:
        When True (default), NaNs in matching positions compare equal.
    msg:
        Optional custom failure message.
    description:
        Optional label for the *Checking:* line.

    Raises
    ------
    AssertionError
        When the shapes differ, the dtypes differ (with ``check_dtype``), or the
        values are not within tolerance.
    """
    import torch  # noqa: PLC0415

    actual_tensor = _as_cpu_tensor(actual)
    expected_tensor = _as_cpu_tensor(expected)

    if actual_tensor.shape != expected_tensor.shape:
        raise AssertionError(
            _build_failure_lines(
                expected=_tensor_detail(expected_tensor),
                actual=_tensor_detail(actual_tensor),
                description=description,
                msg=msg or "The tensors have different shapes.",
            )
        )

    if check_dtype and actual_tensor.dtype != expected_tensor.dtype:
        raise AssertionError(
            _build_failure_lines(
                expected=_tensor_detail(expected_tensor),
                actual=_tensor_detail(actual_tensor),
                description=description,
                msg=msg or "The tensors have different dtypes.",
            )
        )

    target = torch.complex128 if (actual_tensor.is_complex() or expected_tensor.is_complex()) else torch.float64
    actual_cast = actual_tensor.to(target)
    expected_cast = expected_tensor.to(target)

    if torch.allclose(actual_cast, expected_cast, rtol=rtol, atol=atol, equal_nan=equal_nan):
        return

    mismatches = ~torch.isclose(actual_cast, expected_cast, rtol=rtol, atol=atol, equal_nan=equal_nan)
    num_mismatch = int(mismatches.sum().item())
    abs_diff = (actual_cast - expected_cast).abs()
    max_diff = float(torch.nan_to_num(abs_diff, nan=float("inf")).max().item()) if abs_diff.numel() else 0.0
    default_msg = (
        f"The tensors are not close enough (rtol={rtol}, atol={atol}): "
        f"{num_mismatch} of {actual_tensor.numel()} elements differ, "
        f"max absolute difference {max_diff:.3g}."
    )
    raise AssertionError(
        _build_failure_lines(
            expected=_tensor_detail(expected_tensor),
            actual=_tensor_detail(actual_tensor),
            description=description,
            msg=msg or default_msg,
        )
    )


def assert_tensor_equal(
    actual: Any,
    expected: Any,
    *,
    check_dtype: bool = False,
    msg: str | None = None,
    description: str | None = None,
) -> None:
    """Assert two PyTorch tensors are exactly equal.

    Prefer this for integer, boolean, or index tensors where exact equality is meaningful;
    use :func:`assert_tensor_allclose` for floating-point tensors. ``actual`` and ``expected``
    may be anything ``torch.as_tensor`` accepts, and are detached and moved to the CPU before
    comparison.

    Parameters
    ----------
    actual:
        The tensor produced by student code.
    expected:
        The correct / reference tensor.
    check_dtype:
        When True, the two tensors must also share a dtype (default False).
    msg:
        Optional custom failure message.
    description:
        Optional label for the *Checking:* line.

    Raises
    ------
    AssertionError
        When the shapes differ, the dtypes differ (with ``check_dtype``), or any
        elements differ.
    """
    actual_tensor = _as_cpu_tensor(actual)
    expected_tensor = _as_cpu_tensor(expected)

    if actual_tensor.shape != expected_tensor.shape:
        raise AssertionError(
            _build_failure_lines(
                expected=_tensor_detail(expected_tensor),
                actual=_tensor_detail(actual_tensor),
                description=description,
                msg=msg or "The tensors have different shapes.",
            )
        )

    if check_dtype and actual_tensor.dtype != expected_tensor.dtype:
        raise AssertionError(
            _build_failure_lines(
                expected=_tensor_detail(expected_tensor),
                actual=_tensor_detail(actual_tensor),
                description=description,
                msg=msg or "The tensors have different dtypes.",
            )
        )

    elementwise_equal = actual_tensor == expected_tensor
    if bool(elementwise_equal.all()):
        return

    num_mismatch = int((~elementwise_equal).sum().item())
    default_msg = f"The tensors are not equal: {num_mismatch} of {actual_tensor.numel()} elements differ."
    raise AssertionError(
        _build_failure_lines(
            expected=_tensor_detail(expected_tensor),
            actual=_tensor_detail(actual_tensor),
            description=description,
            msg=msg or default_msg,
        )
    )
