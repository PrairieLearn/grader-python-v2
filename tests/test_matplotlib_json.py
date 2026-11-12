import json
from collections.abc import Callable
from datetime import UTC
from datetime import datetime
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pytest
from matplotcheck.base import PlotTester
from matplotlib.colors import to_hex
from matplotlib.figure import Figure

from pytest_prairielearn_grader.json_utils import from_json
from pytest_prairielearn_grader.json_utils import to_json
from pytest_prairielearn_grader.matplotlib_json import UnsupportedPlotError
from pytest_prairielearn_grader.matplotlib_json import plot_from_json


@pytest.fixture(autouse=True)
def close_figures() -> Any:
    # Other tests in this process can leave pyplot figures open.
    plt.close("all")
    yield
    plt.close("all")


def get_suptitle(figure: Any) -> str:
    # The matplotlib stubs don't include Figure.get_suptitle.
    return figure.get_suptitle()


def round_trip(value: Any) -> Any:
    """Send a value through real JSON text, as the sandbox does."""
    return from_json(json.loads(json.dumps(to_json(value))))


def test_semilogy_axes() -> None:
    x = np.arange(0, 11)
    plt.semilogy(x, np.exp(x), label="f", color="red", linewidth=3, linestyle="--", marker="o")
    plt.xlabel("x")
    plt.ylabel("f(x)")
    plt.title("Growth")

    figure = round_trip(plt.gca())

    assert isinstance(figure, Figure)
    assert len(figure.axes) == 1
    # The matplotlib stubs don't type get_yscale correctly.
    axes: Any = figure.axes[0]
    assert axes.get_xscale() == "linear"
    assert axes.get_yscale() == "log"
    assert (axes.get_xlabel(), axes.get_ylabel(), axes.get_title()) == ("x", "f(x)", "Growth")
    assert axes.get_xlim() == plt.gca().get_xlim()
    assert axes.get_ylim() == plt.gca().get_ylim()
    line = axes.get_lines()[0]
    np.testing.assert_allclose(line.get_xdata(), x)
    np.testing.assert_allclose(line.get_ydata(), np.exp(x))
    assert line.get_label() == "f"
    assert to_hex(line.get_color()) == to_hex("red")
    assert line.get_linewidth() == 3
    assert line.get_linestyle() == "--"
    assert line.get_marker() == "o"


def test_figure_value_and_all_subplots_kept() -> None:
    figure, (left, right) = plt.subplots(1, 2)
    left.plot([1, 2], [3, 4])
    right.plot([5, 6], [7, 8])
    figure.suptitle("Both")

    from_figure = round_trip(figure)
    from_axes = round_trip(right)

    for rebuilt in (from_figure, from_axes):
        assert isinstance(rebuilt, Figure)
        assert get_suptitle(rebuilt) == "Both"
        assert len(rebuilt.axes) == 2
        np.testing.assert_allclose(rebuilt.axes[0].get_lines()[0].get_ydata(), [3, 4])
        np.testing.assert_allclose(rebuilt.axes[1].get_lines()[0].get_ydata(), [7, 8])
        assert rebuilt.axes[1].get_position().bounds == right.get_position().bounds


def test_twin_axes_kept_as_separate_axes() -> None:
    _, axes = plt.subplots()
    axes.plot([1, 2], [3, 4])
    twin = axes.twinx()
    twin.plot([1, 2], [50, 60])

    figure = round_trip(axes)

    assert len(figure.axes) == 2
    np.testing.assert_allclose(figure.axes[1].get_lines()[0].get_ydata(), [50, 60])


def test_scatter_values_sizes_and_colors() -> None:
    _, axes = plt.subplots()
    axes.scatter([1, 2, 3], [4, 5, 6], s=[10, 20, 30], c=["red", "green", "blue"], label="points")

    collection = round_trip(axes).axes[0].collections[0]

    np.testing.assert_allclose(collection.get_offsets(), [[1, 4], [2, 5], [3, 6]])
    np.testing.assert_allclose(collection.get_sizes(), [10, 20, 30])
    assert [to_hex(color) for color in collection.get_facecolor()] == [to_hex(color) for color in ("red", "green", "blue")]
    assert collection.get_label() == "points"


def test_bar_with_numpy_values() -> None:
    _, axes = plt.subplots()
    axes.bar(np.array([0, 1, 2]), np.array([5, 6, 7], dtype=np.int64), bottom=np.array([1, 1, 1]), color="green", label="bars")

    rebuilt = round_trip(axes).axes[0]

    assert [patch.get_height() for patch in rebuilt.patches] == [5, 6, 7]
    assert [patch.get_y() for patch in rebuilt.patches] == [1, 1, 1]
    assert [patch.get_x() for patch in rebuilt.patches] == pytest.approx([-0.4, 0.6, 1.6])
    assert to_hex(rebuilt.patches[0].get_facecolor()) == to_hex("green")
    assert rebuilt.containers[0].get_label() == "bars"


def test_horizontal_bars() -> None:
    _, axes = plt.subplots()
    axes.barh([0, 1], [5, 6])

    rebuilt = round_trip(axes).axes[0]

    assert rebuilt.containers[0].orientation == "horizontal"
    assert [patch.get_width() for patch in rebuilt.patches] == [5, 6]


def test_histogram() -> None:
    _, axes = plt.subplots()
    counts, edges, _ = axes.hist([1, 1, 2, 3, 3, 3], bins=3)

    rebuilt = round_trip(axes).axes[0]

    np.testing.assert_allclose([patch.get_height() for patch in rebuilt.patches], counts)
    np.testing.assert_allclose([patch.get_x() for patch in rebuilt.patches], edges[:-1])


def test_categorical_line_and_bar() -> None:
    _, axes = plt.subplots()
    axes.bar(["a", "b"], [1, 2])
    axes.plot(["a", "b"], [3, 4])

    rebuilt = round_trip(axes).axes[0]

    assert list(rebuilt.get_lines()[0].get_xdata()) == ["a", "b"]
    assert [patch.get_height() for patch in rebuilt.patches] == [1, 2]
    assert [patch.get_x() for patch in rebuilt.patches] == pytest.approx([-0.4, 0.6])
    rebuilt.figure.canvas.draw()
    assert [label.get_text() for label in rebuilt.get_xticklabels()] == ["a", "b"]


def test_dates_come_back_as_date_numbers() -> None:
    _, axes = plt.subplots()
    axes.plot([datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 1, 2, tzinfo=UTC)], [1, 2])
    expected = axes.get_lines()[0].get_xdata(orig=False)

    rebuilt = round_trip(axes).axes[0]

    np.testing.assert_allclose(rebuilt.get_lines()[0].get_xdata(), expected)
    assert type(rebuilt.xaxis.get_converter()).__module__ == "matplotlib.dates"


def test_nan_infinity_and_masked_values() -> None:
    _, axes = plt.subplots()
    axes.plot([1, 2, 3], [1.0, float("nan"), float("inf")])
    axes.plot([1, 2], np.ma.masked_array([1.0, 2.0], mask=[False, True]))
    axes.set_ylim(0, 5)

    lines = round_trip(axes).axes[0].get_lines()

    np.testing.assert_array_equal(lines[0].get_ydata(), [1.0, float("nan"), float("inf")])
    np.testing.assert_array_equal(lines[1].get_ydata(), [1.0, float("nan")])


def test_empty_axes() -> None:
    _, axes = plt.subplots()

    rebuilt = round_trip(axes)

    assert len(rebuilt.axes) == 1
    assert not rebuilt.axes[0].get_lines()


def test_legend_labels_kept() -> None:
    _, axes = plt.subplots()
    axes.plot([1, 2], [3, 4], label="data")
    axes.legend(title="Key")

    legend = round_trip(axes).axes[0].get_legend()

    assert [text.get_text() for text in legend.get_texts()] == ["data"]
    assert legend.get_title().get_text() == "Key"


def test_rebuilt_figure_can_be_drawn() -> None:
    _, axes = plt.subplots()
    axes.plot([1, 2], [3, 4], label="data")
    axes.scatter([1], [2])
    axes.bar([1], [2])
    axes.legend()

    round_trip(axes).canvas.draw()


def test_rebuild_does_not_touch_pyplot_figures() -> None:
    plt.plot([1, 2], [3, 4])
    before = plt.get_fignums()

    round_trip(plt.gca())

    assert plt.get_fignums() == before


def test_plot_tester_works_on_rebuilt_figure() -> None:
    plt.plot([1, 2, 3], [2, 4, 6], label="doubled")
    plt.xlabel("Input")
    plt.ylabel("Output")
    plt.title("Doubling")
    plt.legend()

    tester = PlotTester(round_trip(plt.gca()).axes[0])

    tester.assert_plot_type("line")
    tester.assert_axis_label_contains(axis="x", strings_expected=["Input"])
    tester.assert_axis_label_contains(axis="y", strings_expected=["Output"])
    tester.assert_title_contains(["Doubling"])
    tester.assert_legend_labels(["doubled"])


def _errorbar(axes: Any) -> None:
    axes.errorbar([1, 2], [3, 4], yerr=[0.1, 0.2])


def _bar_with_errors(axes: Any) -> None:
    axes.bar([1, 2], [3, 4], yerr=[0.1, 0.2])


def _stem(axes: Any) -> None:
    axes.stem([1, 2], [3, 4])


def _image(axes: Any) -> None:
    axes.imshow([[1, 2], [3, 4]])


def _text(axes: Any) -> None:
    axes.plot([1, 2], [3, 4])
    axes.text(1, 3, "note")


def _annotation(axes: Any) -> None:
    axes.annotate("note", (1, 3))


def _axhline(axes: Any) -> None:
    axes.plot([1, 2], [3, 4])
    axes.axhline(3)


def _axline(axes: Any) -> None:
    axes.axline((0, 0), slope=1)


def _axes_coordinates(axes: Any) -> None:
    axes.plot([0, 1], [0, 1], transform=axes.transAxes)


def _blended_coordinates(axes: Any) -> None:
    axes.plot([0, 1], [0, 1], transform=axes.get_xaxis_transform())


def _bar_axes_coordinates(axes: Any) -> None:
    axes.bar([0, 1], [0, 1], transform=axes.transAxes)


def _scatter_axes_coordinates(axes: Any) -> None:
    axes.scatter([0, 1], [0, 1], transform=axes.transAxes)


def _fill_between(axes: Any) -> None:
    axes.fill_between([1, 2], [3, 4])


def _pie(axes: Any) -> None:
    axes.pie([1, 2])


def _colormapped_scatter(axes: Any) -> None:
    axes.scatter([1, 2], [3, 4], c=[1.0, 2.0])


def _vlines(axes: Any) -> None:
    axes.vlines([1, 2], 0, 1)


def _contour(axes: Any) -> None:
    axes.contourf([[1, 2], [3, 4]])


def _step_histogram(axes: Any) -> None:
    axes.hist([1, 2, 3], histtype="step")


def _rectangle_patch(axes: Any) -> None:
    axes.axvspan(1, 2)


def _inset(axes: Any) -> None:
    axes.inset_axes([0.5, 0.5, 0.2, 0.2])


def _function_scale(axes: Any) -> None:
    axes.set_yscale("function", functions=(lambda v: v, lambda v: v))


@pytest.mark.parametrize(
    ("draw", "message"),
    [
        (_errorbar, "errorbar"),
        (_bar_with_errors, "errorbar"),
        (_stem, "stem"),
        (_image, "images"),
        (_text, "text"),
        (_annotation, "text"),
        (_axhline, "axhline"),
        (_axline, "AxLine"),
        (_axes_coordinates, "data coordinates"),
        (_blended_coordinates, "data coordinates"),
        (_bar_axes_coordinates, "data coordinates"),
        (_scatter_axes_coordinates, "data coordinates"),
        (_fill_between, "plots"),
        (_pie, "aren't supported"),
        (_colormapped_scatter, "colormap"),
        (_vlines, "LineCollection"),
        (_contour, "aren't supported"),
        (_step_histogram, "Polygon"),
        (_rectangle_patch, "Rectangle"),
        (_inset, "inset"),
        (_function_scale, "function"),
    ],
)
def test_unsupported_plots_are_rejected(draw: Callable[[Any], None], message: str) -> None:
    _, axes = plt.subplots()
    draw(axes)

    with pytest.raises(UnsupportedPlotError, match=message):
        to_json(axes)
    with pytest.raises(UnsupportedPlotError, match=message):
        to_json(axes.figure)


def test_polar_axes_rejected() -> None:
    _, axes = plt.subplots(subplot_kw={"projection": "polar"})

    with pytest.raises(UnsupportedPlotError, match="polar"):
        to_json(axes)


def test_rejection_in_any_subplot_rejects_whole_figure() -> None:
    _, (left, right) = plt.subplots(1, 2)
    left.plot([1, 2], [3, 4])
    _errorbar(right)

    with pytest.raises(UnsupportedPlotError, match="errorbar"):
        to_json(left)


def test_figure_level_items_rejected() -> None:
    figure = plt.figure()
    figure.text(0.5, 0.5, "note")

    with pytest.raises(UnsupportedPlotError, match="directly to a figure"):
        to_json(figure)


def test_subfigures_rejected() -> None:
    figure = plt.figure()
    sub = figure.subfigures(1, 2)
    axes = sub[0].subplots()

    with pytest.raises(UnsupportedPlotError, match="subfigures"):
        to_json(figure)
    with pytest.raises(UnsupportedPlotError, match="top-level figure"):
        to_json(axes)


def valid_data() -> dict[str, Any]:
    _, axes = plt.subplots()
    axes.plot([1, 2], [3, 4], label="line")
    axes.scatter([1], [2])
    axes.bar([1], [2])
    axes.legend()
    return json.loads(json.dumps(to_json(axes)))["_value"]


def _set(path: list[Any], value: Any) -> Callable[[dict[str, Any]], None]:
    def change(data: dict[str, Any]) -> None:
        target: Any = data
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    return change


def _delete(path: list[Any]) -> Callable[[dict[str, Any]], None]:
    def change(data: dict[str, Any]) -> None:
        target: Any = data
        for key in path[:-1]:
            target = target[key]
        del target[path[-1]]

    return change


LINE = ["axes", 0, "lines", 0]


@pytest.mark.parametrize(
    "change",
    [
        _set(["axes"], "not a list"),
        _set(["size"], [1]),
        _set(["size"], [0, 1]),
        _set(["size"], [1e9, 1]),
        _set(["size"], [float("nan"), 1]),
        _set(["suptitle"], 5),
        _delete(["axes", 0, "lines"]),
        _set(["axes", 0], []),
        _set(["axes", 0, "position"], [0, 0, 1]),
        _set(["axes", 0, "x_axis", "scale"], "__import__('os')"),
        _set(["axes", 0, "x_axis", "units"], "other"),
        _set(["axes", 0, "x_limits"], [float("nan"), 1]),
        _set(["axes", 0, "x_limits"], ["0", "1"]),
        _set([*LINE, "x"], "12"),
        _set([*LINE, "x"], ["1", "2"]),
        _set([*LINE, "x"], [True, False]),
        _set([*LINE, "x"], [[1], [2]]),
        _set([*LINE, "x"], [1]),
        _set([*LINE, "color"], "not a color"),
        _set([*LINE, "color"], {"a": 1}),
        _set([*LINE, "linestyle"], "wavy"),
        _set([*LINE, "drawstyle"], "wavy"),
        _set([*LINE, "marker"], "not a marker"),
        _set([*LINE, "marker"], 5),
        _set([*LINE, "linewidth"], "wide"),
        _set(["axes", 0, "bars", 0, "orientation"], "diagonal"),
        _set(["axes", 0, "bars", 0, "height"], []),
        _set(["axes", 0, "scatters", 0, "x"], []),
        _set(["axes", 0, "legend", "labels"], "line"),
        _set(["axes", 0, "title"], "title"),
    ],
)
def test_malformed_data_raises_value_error(change: Callable[[dict[str, Any]], None]) -> None:
    data = valid_data()
    change(data)

    with pytest.raises(ValueError, match="matplotlib_figure has invalid data"):
        plot_from_json(data)


def test_category_value_out_of_range_rejected() -> None:
    _, axes = plt.subplots()
    axes.plot(["a", "b"], [1, 2])
    data = json.loads(json.dumps(to_json(axes)))["_value"]
    data["axes"][0]["lines"][0]["x"] = [0, 5]

    with pytest.raises(ValueError, match="matplotlib_figure has invalid data"):
        plot_from_json(data)


def test_missing_value_rejected() -> None:
    with pytest.raises(ValueError, match="should have value"):
        from_json({"_type": "matplotlib_figure"})


def test_other_matplotlib_values_are_not_converted() -> None:
    line = plt.plot([1, 2], [3, 4])[0]

    assert to_json(line) is line
