import subprocess
import sys
from collections.abc import Callable
from typing import Any

import numpy as np
import pytest
from matplotlib.figure import Figure

from pytest_prairielearn_grader.assertions import assert_plot_equal
from pytest_prairielearn_grader.matplotlib_json import plot_from_json
from pytest_prairielearn_grader.matplotlib_json import plot_to_json

X = np.arange(0, 11)

Draw = Callable[[Any], object]


def make_plot(draw: Draw, subplots: int = 1) -> Figure:
    figure = Figure()
    axes = figure.subplots(1, subplots, squeeze=False)[0]
    for subplot in axes:
        draw(subplot)
    return figure


def semilogy(axes: Any) -> Any:
    return axes.semilogy(X, np.exp(X), label="exp")


def two_lines(axes: Any) -> None:
    axes.plot(X, X, label="linear")
    axes.plot(X, X**2, label="square")


def full_plot(axes: Any) -> None:
    axes.plot(X, X**2, "r--o", label="square")
    axes.scatter([3, 1, 2], [6, 2, 4], color="green", label="points")
    axes.bar([4, 6, 8], [1, 2, 3], color="purple", label="bars")
    axes.set_xlabel("Input")
    axes.set_ylabel("Output")
    axes.set_title("Results")
    axes.set_title("left", loc="left")
    axes.set_xlim(-1, 12)
    axes.legend(title="Key")


@pytest.mark.parametrize(
    ("student", "reference", "options"),
    [
        pytest.param(semilogy, semilogy, {}, id="same"),
        pytest.param(lambda a: a.semilogy(X, np.exp(X) * (1 + 1e-7)), semilogy, {}, id="within-tolerance"),
        pytest.param(lambda a: a.semilogy(X, np.exp(X) * 1.01), semilogy, {"rtol": 0.02}, id="custom-tolerance"),
        pytest.param(lambda a: a.semilogy(X[::-1], np.exp(X[::-1])), semilogy, {}, id="reversed-line"),
        pytest.param(lambda a: (a.plot(X, X**2), a.plot(X, X)), two_lines, {}, id="lines-any-order"),
        pytest.param(
            lambda a: (a.plot(X, X**2, label="same"), a.plot(X, X, label="same")),
            lambda a: (a.plot(X, X, label="same"), a.plot(X, X**2, label="same")),
            {},
            id="same-labels-any-order",
        ),
        pytest.param(lambda a: a.scatter([2, 1, 3], [4, 2, 6]), lambda a: a.scatter([1, 2, 3], [2, 4, 6]), {}, id="scatter-any-order"),
        pytest.param(lambda a: a.bar([2, 1], [5, 4]), lambda a: a.bar([1, 2], [4, 5]), {}, id="bars-any-order"),
        pytest.param(lambda a: (semilogy(a), a.plot(X, X)), semilogy, {"allow_extra": True}, id="allow-extra"),
        pytest.param(lambda a: (a.semilogy(X, np.exp(X), "r:"), a.set_xlabel("other")), semilogy, {}, id="labels-and-styles-unchecked"),
        pytest.param(lambda a: a.plot(X, X), semilogy, {"check_scales": False, "check_data": False}, id="nothing-checked"),
        pytest.param(
            full_plot,
            full_plot,
            {"check_labels": True, "check_titles": True, "check_legend": True, "check_limits": True, "check_styles": True},
            id="everything",
        ),
    ],
)
def test_matching_plots(student: Draw, reference: Draw, options: dict[str, Any]) -> None:
    assert_plot_equal(make_plot(student), make_plot(reference), **options)


def test_axes_and_figures_can_be_mixed() -> None:
    student = make_plot(semilogy)
    reference = make_plot(semilogy)
    assert_plot_equal(student.axes[0], reference)
    assert_plot_equal(student, reference.axes[0])


def test_plot_sent_from_the_sandbox_matches() -> None:
    reference = make_plot(full_plot, subplots=2)
    student = plot_from_json(plot_to_json(make_plot(full_plot, subplots=2))["_value"])
    assert_plot_equal(
        student,
        reference,
        ordered=True,
        check_labels=True,
        check_titles=True,
        check_legend=True,
        check_limits=True,
        check_styles=True,
    )


@pytest.mark.parametrize(
    ("student", "reference", "options", "message"),
    [
        pytest.param(
            lambda a: a.plot(X, np.exp(X)),
            semilogy,
            {},
            "Expected a log scale on the y-axis of your plot, but found a linear scale.",
            id="scale",
        ),
        pytest.param(
            lambda a: (semilogy(a), a.semilogy(X, X)), semilogy, {}, "Expected 1 line in your plot, but found 2.", id="line-count"
        ),
        pytest.param(
            lambda a: a.semilogy(X, np.exp(X) * 1.01), semilogy, {}, "No line in your plot matches the line labeled 'exp'.", id="data"
        ),
        pytest.param(
            lambda a: a.semilogy(X, np.exp(X) * 2),
            lambda a: a.semilogy(X, np.exp(X)),
            {},
            "No line in your plot matches the expected line.",
            id="unlabeled",
        ),
        pytest.param(
            lambda a: a.semilogy(X[[1, 0, *range(2, 11)]], np.exp(X[[1, 0, *range(2, 11)]])),
            semilogy,
            {},
            "No line in your plot matches",
            id="scrambled-line",
        ),
        pytest.param(
            lambda a: (a.plot(X, X**2), a.plot(X, X)),
            two_lines,
            {"ordered": True},
            "Line 1 in your plot doesn't match the line labeled 'linear'.",
            id="ordered",
        ),
        pytest.param(
            lambda a: a.set_yscale("log"),
            semilogy,
            {"allow_extra": True},
            "Expected at least 1 line in your plot, but found 0.",
            id="allow-extra-still-needs-reference",
        ),
        pytest.param(
            lambda a: a.scatter([1, 2], [2, 5]),
            lambda a: a.scatter([1, 2], [2, 4]),
            {},
            "No scatter plot in your plot matches the expected scatter plot.",
            id="scatter",
        ),
        pytest.param(
            lambda a: a.barh([1, 2], [4, 5]), lambda a: a.bar([1, 2], [4, 5]), {}, "No bar plot in your plot matches", id="bar-orientation"
        ),
        pytest.param(
            lambda a: (semilogy(a), a.set_xlabel("X")),
            lambda a: (semilogy(a), a.set_xlabel("x")),
            {"check_labels": True},
            "Expected the x-axis label 'x' in your plot, but found 'X'.",
            id="label",
        ),
        pytest.param(
            semilogy,
            lambda a: (semilogy(a), a.set_title("Growth")),
            {"check_titles": True},
            "Expected the title 'Growth' in your plot, but found ''.",
            id="title",
        ),
        pytest.param(
            semilogy,
            lambda a: (semilogy(a), a.figure.suptitle("All")),
            {"check_titles": True},
            "Expected the figure title 'All' in your plot, but found ''.",
            id="suptitle",
        ),
        pytest.param(
            semilogy,
            lambda a: (semilogy(a), a.legend()),
            {"check_legend": True},
            "Expected a legend with labels ['exp'] in your plot, but found no legend.",
            id="legend",
        ),
        pytest.param(
            lambda a: (semilogy(a), a.set_xlim(0, 12)),
            lambda a: (semilogy(a), a.set_xlim(0, 10)),
            {"check_limits": True},
            "Expected x-axis limits (0, 10) in your plot, but found (0, 12).",
            id="limits",
        ),
        pytest.param(
            lambda a: a.semilogy(X, np.exp(X), color="red", label="exp"),
            lambda a: a.semilogy(X, np.exp(X), color="blue", label="exp"),
            {"check_styles": True},
            "Expected the line labeled 'exp' in your plot to have color #0000ffff, but found #ff0000ff.",
            id="line-color",
        ),
        pytest.param(
            lambda a: a.semilogy(X, np.exp(X), "o"),
            lambda a: a.semilogy(X, np.exp(X), "x"),
            {"check_styles": True, "check_data": False},
            "to have marker x, but found o.",
            id="marker",
        ),
        pytest.param(
            lambda a: a.bar([1, 2], [4, 5], color="red"),
            lambda a: a.bar([1, 2], [4, 5]),
            {"check_styles": True},
            "Expected the expected bar plot in your plot to have colors #1f77b4ff, but found #ff0000ff.",
            id="bar-color",
        ),
        pytest.param(
            lambda a: a.plot(X, X),
            semilogy,
            {"name": "plot"},
            "Expected a log scale on the y-axis of plot, but found a linear scale.",
            id="name",
        ),
        pytest.param(lambda a: a.plot(X, X), semilogy, {"msg": "Check your plot."}, "Check your plot.", id="msg"),
    ],
)
def test_mismatched_plots(student: Draw, reference: Draw, options: dict[str, Any], message: str) -> None:
    with pytest.raises(AssertionError) as e:
        assert_plot_equal(make_plot(student), make_plot(reference), **options)
    assert message in str(e.value)


def test_subplots_are_named_in_messages() -> None:
    student = make_plot(semilogy, subplots=2)
    student.axes[1].set_yscale("linear")
    with pytest.raises(AssertionError, match="y-axis of subplot 2 of your plot"):
        assert_plot_equal(student, make_plot(semilogy, subplots=2))


def test_subplot_count() -> None:
    with pytest.raises(AssertionError, match=r"^Expected 1 set of axes in your plot, but found 2\.$"):
        assert_plot_equal(make_plot(semilogy, subplots=2), make_plot(semilogy))


@pytest.mark.parametrize("value", [5, None, "plot"])
def test_student_value_that_is_not_a_plot(value: Any) -> None:
    with pytest.raises(
        AssertionError, match=f"Expected your plot to be a Matplotlib plot, such as plt.gca\\(\\), but found {type(value).__name__}"
    ):
        assert_plot_equal(value, make_plot(semilogy))


def test_reference_that_is_not_a_plot() -> None:
    with pytest.raises(TypeError, match="reference plot"):
        assert_plot_equal(make_plot(semilogy), [1, 2, 3])


def test_grader_works_without_matplotlib_or_numpy() -> None:
    # The lite image has neither, so importing the grader mustn't import them.
    code = """
import sys
sys.modules["matplotlib"] = None
sys.modules["numpy"] = None
import pytest_prairielearn_grader.plugin
from pytest_prairielearn_grader.assertions import assert_equal, assert_plot_equal
from pytest_prairielearn_grader.fixture import FeedbackFixture
assert_equal(1, 1)
FeedbackFixture("test").add_image(b"png")
try:
    assert_plot_equal(None, None)
except ImportError:
    print("ok")
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert result.stdout == "ok\n"
