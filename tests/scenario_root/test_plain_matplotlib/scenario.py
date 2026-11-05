import numpy as np
import pytest
from matplotcheck.base import PlotTester
from matplotlib.figure import Figure

from pytest_prairielearn_grader.assertions import assert_true
from pytest_prairielearn_grader.fixture import StudentFixture
from pytest_prairielearn_grader.utils import GradingOutputLevel
from pytest_prairielearn_grader.utils import QueryStatusCode

# Importing matplotlib in student code can take longer than the default timeout.
sandbox_timeout = 30.0

EXPECTED_ERROR = (
    "Variable 'errorbar_plot' has a value of type Axes, which can't be sent back to the grader: errorbar plots aren't supported"
)


def check_semilogy(figure: Figure) -> None:
    assert isinstance(figure, Figure)
    assert len(figure.axes) == 1
    axes = figure.axes[0]
    assert axes.get_xscale() == "linear"
    assert axes.get_yscale() == "log"
    x, y = axes.get_lines()[0].get_data()
    np.testing.assert_allclose(np.asarray(x, dtype=float), np.arange(0, 11))
    np.testing.assert_allclose(np.asarray(y, dtype=float), np.exp(np.arange(0, 11)))


@pytest.mark.grading_data(name="query_axes", points=1)
def test_query_axes(sandbox: StudentFixture) -> None:
    check_semilogy(sandbox.query("plot"))


@pytest.mark.grading_data(name="query_figure", points=1)
def test_query_figure(sandbox: StudentFixture) -> None:
    check_semilogy(sandbox.query("figure"))


@pytest.mark.grading_data(name="query_function", points=1)
def test_function_returning_axes_works_with_plot_tester(sandbox: StudentFixture) -> None:
    tester = PlotTester(sandbox.query_function("make_axes").axes[0])

    tester.assert_plot_type("line")
    tester.assert_axis_label_contains(axis="x", strings_expected=["Input"])
    tester.assert_axis_label_contains(axis="y", strings_expected=["Output"])
    tester.assert_title_contains(["Doubling"])
    tester.assert_legend_labels(["doubled"])


@pytest.mark.grading_data(name="subplots", points=1)
def test_function_returning_subplots(sandbox: StudentFixture) -> None:
    figure = sandbox.query_function("make_subplots")

    assert len(figure.axes) == 2
    np.testing.assert_allclose(figure.axes[0].collections[0].get_offsets(), [[1, 3], [2, 4]])
    assert [patch.get_height() for patch in figure.axes[1].patches] == [5, 6]


@pytest.mark.grading_data(name="rejected_raw", points=1)
def test_rejected_plot_keeps_sandbox_usable(sandbox: StudentFixture) -> None:
    response = sandbox.query_raw("errorbar_plot")

    assert response["status"] == QueryStatusCode.NOT_SERIALIZABLE
    assert response["error"] is not None
    assert EXPECTED_ERROR in response["error"]
    check_semilogy(sandbox.query("plot"))


@pytest.mark.output(level=GradingOutputLevel.Friendly)
@pytest.mark.grading_data(name="rejected_message", points=1)
def test_rejected_plot_shows_clear_message(sandbox: StudentFixture) -> None:
    assert_true(isinstance(sandbox.query("errorbar_plot"), Figure), msg="plot is not a Figure")
