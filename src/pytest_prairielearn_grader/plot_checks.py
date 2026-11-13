"""
Compare a student's matplotlib plot with a reference plot, for assertions.assert_plot_equal.

matplotlib is an optional dependency, so assertions only imports this module when a plot is checked.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from matplotlib.axes import Axes
from matplotlib.collections import PathCollection
from matplotlib.colors import to_hex
from matplotlib.container import BarContainer
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.text import Annotation
from matplotlib.text import Text

from .matplotlib_json import reference_line_orientation


@dataclass(frozen=True, slots=True)
class Series:
    kind: str
    label: str
    data: list[np.ndarray]
    # Every series can be compared as given; lines can also be drawn in reverse.
    reversible: bool
    styles: dict[str, Any]

    @property
    def has_label(self) -> bool:
        # matplotlib gives unlabeled artists names such as "_child0".
        return bool(self.label) and not self.label.startswith("_")


@dataclass(frozen=True, slots=True)
class Options:
    name: str
    rtol: float
    atol: float
    check_scales: bool
    check_data: bool
    ordered: bool
    allow_extra: bool
    check_labels: bool
    check_titles: bool
    check_legend: bool
    check_limits: bool
    check_styles: bool
    check_texts: bool


class Mismatch(Exception):
    pass


def plot_mismatch(plot: Any, expected: Any, **options: Any) -> str | None:
    """Return a message describing how plot differs from expected, or None if they match."""
    opts = Options(**options)
    if not isinstance(expected, Axes | Figure):
        raise TypeError(f"assert_plot_equal expects a matplotlib Figure or Axes as the reference plot, not {type(expected).__name__}")
    try:
        _compare(plot, expected, opts)
    except Mismatch as e:
        return str(e)
    return None


def _axes_of(value: Any) -> list[Any]:
    return [value] if isinstance(value, Axes) else list(value.axes)


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _compare(plot: Any, expected: Any, opts: Options) -> None:
    if not isinstance(plot, Axes | Figure):
        raise Mismatch(f"Expected {opts.name} to be a Matplotlib plot, such as plt.gca(), but found {type(plot).__name__}.")

    plot_axes = _axes_of(plot)
    expected_axes = _axes_of(expected)
    if len(plot_axes) != len(expected_axes):
        raise Mismatch(f"Expected {_plural(len(expected_axes), 'set')} of axes in {opts.name}, but found {len(plot_axes)}.")

    if opts.check_titles:
        actual_title = _figure_of(plot).get_suptitle()
        expected_title = _figure_of(expected).get_suptitle()
        if actual_title != expected_title:
            raise Mismatch(f"Expected the figure title {expected_title!r} in {opts.name}, but found {actual_title!r}.")

    for index, (actual, reference) in enumerate(zip(plot_axes, expected_axes, strict=True)):
        where = opts.name if len(expected_axes) == 1 else f"subplot {index + 1} of {opts.name}"
        _compare_axes(actual, reference, where, opts)


def _figure_of(value: Any) -> Any:
    return value.figure if isinstance(value, Axes) else value


def _compare_axes(actual: Any, reference: Any, where: str, opts: Options) -> None:
    if opts.check_scales:
        for axis in ("x", "y"):
            actual_scale = getattr(actual, f"get_{axis}scale")()
            expected_scale = getattr(reference, f"get_{axis}scale")()
            if actual_scale != expected_scale:
                raise Mismatch(f"Expected a {expected_scale} scale on the {axis}-axis of {where}, but found a {actual_scale} scale.")

    if opts.check_data or opts.check_styles:
        for kind, extract in (
            ("line", _lines),
            ("horizontal line", _horizontal_lines),
            ("vertical line", _vertical_lines),
            ("scatter plot", _scatters),
            ("bar plot", _bars),
        ):
            _compare_series(extract(actual), extract(reference), kind, where, opts)

    if opts.check_texts:
        _compare_texts(_texts(actual), _texts(reference), where, opts)

    if opts.check_limits:
        for axis in ("x", "y"):
            actual_limits = getattr(actual, f"get_{axis}lim")()
            expected_limits = getattr(reference, f"get_{axis}lim")()
            if not np.allclose(actual_limits, expected_limits, rtol=opts.rtol, atol=opts.atol):
                raise Mismatch(
                    f"Expected {axis}-axis limits {_format_limits(expected_limits)} in {where}, but found {_format_limits(actual_limits)}."
                )

    if opts.check_labels:
        for axis in ("x", "y"):
            actual_label = getattr(actual, f"get_{axis}label")()
            expected_label = getattr(reference, f"get_{axis}label")()
            if actual_label != expected_label:
                raise Mismatch(f"Expected the {axis}-axis label {expected_label!r} in {where}, but found {actual_label!r}.")

    if opts.check_titles:
        for location in ("center", "left", "right"):
            actual_title = actual.get_title(loc=location)
            expected_title = reference.get_title(loc=location)
            if actual_title != expected_title:
                title = "title" if location == "center" else f"{location} title"
                raise Mismatch(f"Expected the {title} {expected_title!r} in {where}, but found {actual_title!r}.")

    if opts.check_legend:
        actual_legend = _legend(actual)
        expected_legend = _legend(reference)
        if not opts.ordered and actual_legend is not None and expected_legend is not None:
            actual_legend = (actual_legend[0], sorted(actual_legend[1]))
            expected_legend = (expected_legend[0], sorted(expected_legend[1]))
        if actual_legend != expected_legend:
            raise Mismatch(f"Expected {_describe_legend(expected_legend)} in {where}, but found {_describe_legend(actual_legend)}.")


def _format_limits(limits: Any) -> str:
    low, high = limits
    return f"({low:g}, {high:g})"


def _legend(axes: Any) -> tuple[str, list[str]] | None:
    legend = axes.get_legend()
    if legend is None:
        return None
    return legend.get_title().get_text(), [text.get_text() for text in legend.get_texts()]


def _describe_legend(legend: tuple[str, list[str]] | None) -> str:
    if legend is None:
        return "no legend"
    title, labels = legend
    description = f"a legend with labels {labels}"
    return f"{description} and title {title!r}" if title else description


def _floats(values: Any) -> np.ndarray:
    return np.asarray(values, dtype=float).ravel()


def _hex(color: Any) -> str:
    return to_hex(color, keep_alpha=True)


def _lines(axes: Any) -> list[Series]:
    return [
        Series(
            kind="line",
            label=str(line.get_label()),
            data=[_floats(line.get_xdata(orig=False)), _floats(line.get_ydata(orig=False))],
            reversible=True,
            styles={
                "color": _hex(line.get_color()),
                "line style": line.get_linestyle(),
                "marker": line.get_marker(),
            },
        )
        for line in axes.lines
        if type(line) is Line2D and line.get_transform() is axes.transData
    ]


def _reference_lines(axes: Any, orientation: str) -> list[Series]:
    series = []
    for line in axes.lines:
        if type(line) is not Line2D or reference_line_orientation(axes, line) != orientation:
            continue
        # The value is in data coordinates, and the extent along the line is a fraction of the axes.
        if orientation == "horizontal":
            value, extent = line.get_ydata(orig=False), line.get_xdata()
        else:
            value, extent = line.get_xdata(orig=False), line.get_ydata()
        series.append(
            Series(
                kind=f"{orientation} line",
                label=str(line.get_label()),
                data=[_floats(value)[:1], _floats(extent)],
                reversible=False,
                styles={"color": _hex(line.get_color()), "line style": line.get_linestyle()},
            )
        )
    return series


def _horizontal_lines(axes: Any) -> list[Series]:
    return _reference_lines(axes, "horizontal")


def _vertical_lines(axes: Any) -> list[Series]:
    return _reference_lines(axes, "vertical")


@dataclass(frozen=True, slots=True)
class PlotText:
    kind: str
    text: str
    # The annotated point for an annotation. Plain text is matched by its string alone.
    point: np.ndarray | None
    coordinates: str


def _texts(axes: Any) -> list[PlotText]:
    texts = []
    for text in axes.texts:
        if type(text) is Annotation:
            # Typed as Any because the matplotlib stubs don't include an annotation's xy.
            annotation: Any = text
            coordinates = "data" if annotation.xycoords == "data" else "axes"
            point = annotation.xy
            if coordinates == "data":
                point = (axes.xaxis.convert_units(point[0]), axes.yaxis.convert_units(point[1]))
            texts.append(PlotText("annotation", text.get_text(), _floats(point), coordinates))
        elif type(text) is Text:
            texts.append(PlotText("text", text.get_text(), None, "data"))
    return texts


def _format_point(point: np.ndarray, coordinates: str) -> str:
    position = f"({point[0]:g}, {point[1]:g})"
    return position if coordinates == "data" else f"{position} in axes coordinates"


def _compare_texts(actual: list[PlotText], expected: list[PlotText], where: str, opts: Options) -> None:
    for kind in ("text", "annotation"):
        actual_count = sum(text.kind == kind for text in actual)
        expected_count = sum(text.kind == kind for text in expected)
        if opts.allow_extra:
            if actual_count < expected_count:
                raise Mismatch(f"Expected at least {_plural(expected_count, kind)} in {where}, but found {actual_count}.")
        elif actual_count != expected_count:
            raise Mismatch(f"Expected {_plural(expected_count, kind)} in {where}, but found {actual_count}.")

    def matches(candidate: PlotText, reference: PlotText) -> bool:
        if candidate.kind != reference.kind or candidate.text != reference.text:
            return False
        if reference.point is None or candidate.point is None:
            return True
        return candidate.coordinates == reference.coordinates and np.allclose(
            candidate.point, reference.point, rtol=opts.rtol, atol=opts.atol
        )

    remaining = list(actual)
    for reference in expected:
        position = next((i for i, candidate in enumerate(remaining) if matches(candidate, reference)), None)
        if position is not None:
            remaining.pop(position)
            continue
        same_text = next((text for text in remaining if text.kind == reference.kind and text.text == reference.text), None)
        if reference.point is not None and same_text is not None and same_text.point is not None:
            raise Mismatch(
                f"Expected the annotation {reference.text!r} in {where} to point at {_format_point(reference.point, reference.coordinates)}, "
                f"but it points at {_format_point(same_text.point, same_text.coordinates)}."
            )
        raise Mismatch(f"Expected the {reference.kind} {reference.text!r} in {where}, but didn't find it.")


def _sorted_points(columns: list[np.ndarray], colors: list[str]) -> tuple[list[np.ndarray], list[str]]:
    """Sort points so that the order they were plotted in doesn't matter."""
    order = np.lexsort(columns[::-1]) if len(columns[0]) else np.arange(0)
    return [column[order] for column in columns], [colors[i] for i in order]


def _scatters(axes: Any) -> list[Series]:
    series = []
    for collection in axes.collections:
        if type(collection) is not PathCollection:
            continue
        offsets = np.asarray(collection.get_offsets(), dtype=float).reshape(-1, 2)
        count = len(offsets)
        facecolors = collection.get_facecolor()
        colors = [_hex(facecolors[i % len(facecolors)]) for i in range(count)] if len(facecolors) else ["none"] * count
        data, colors = _sorted_points([offsets[:, 0], offsets[:, 1]], colors)
        series.append(
            Series(kind="scatter plot", label=str(collection.get_label()), data=data, reversible=False, styles={"colors": colors})
        )
    return series


def _bars(axes: Any) -> list[Series]:
    series = []
    # Typed as Any because the matplotlib stubs don't let get_label be called on a container.
    containers: list[Any] = [container for container in axes.containers if isinstance(container, BarContainer)]
    for container in containers:
        patches = container.patches
        columns = [
            _floats([patch.get_x() for patch in patches]),
            _floats([patch.get_y() for patch in patches]),
            _floats([patch.get_width() for patch in patches]),
            _floats([patch.get_height() for patch in patches]),
        ]
        data, colors = _sorted_points(columns, [_hex(patch.get_facecolor()) for patch in patches])
        series.append(
            Series(
                kind="bar plot",
                label=str(container.get_label()),
                data=data,
                reversible=False,
                styles={"orientation": container.orientation, "colors": colors},
            )
        )
    return series


def _data_matches(actual: Series, expected: Series, opts: Options) -> bool:
    def close(columns: list[np.ndarray]) -> bool:
        return all(
            column.shape == reference.shape and np.allclose(column, reference, rtol=opts.rtol, atol=opts.atol, equal_nan=True)
            for column, reference in zip(columns, expected.data, strict=True)
        )

    if actual.styles.get("orientation") != expected.styles.get("orientation"):
        return False
    if close(actual.data):
        return True
    return expected.reversible and close([column[::-1] for column in actual.data])


def _compare_series(actual: list[Series], expected: list[Series], kind: str, where: str, opts: Options) -> None:
    if opts.allow_extra:
        if len(actual) < len(expected):
            raise Mismatch(f"Expected at least {_plural(len(expected), kind)} in {where}, but found {len(actual)}.")
    elif len(actual) != len(expected):
        raise Mismatch(f"Expected {_plural(len(expected), kind)} in {where}, but found {len(actual)}.")

    def describe(index: int) -> str:
        series = expected[index]
        if series.has_label:
            return f"the {kind} labeled {series.label!r}"
        return f"the expected {kind}" if len(expected) == 1 else f"expected {kind} {index + 1}"

    pairs: list[tuple[Series, int]] = []
    if opts.ordered:
        for index, series in enumerate(expected):
            if opts.check_data and not _data_matches(actual[index], series, opts):
                raise Mismatch(f"{kind.capitalize()} {index + 1} in {where} doesn't match {describe(index)}.")
            pairs.append((actual[index], index))
    else:
        remaining = list(actual)
        for index, series in enumerate(expected):
            position = next(
                (i for i, candidate in enumerate(remaining) if not opts.check_data or _data_matches(candidate, series, opts)),
                None,
            )
            if position is None:
                raise Mismatch(f"No {kind} in {where} matches {describe(index)}.")
            pairs.append((remaining.pop(position), index))

    if opts.check_styles:
        for match, index in pairs:
            for style, expected_value in expected[index].styles.items():
                if match.styles[style] != expected_value:
                    raise Mismatch(
                        f"Expected {describe(index)} in {where} to have {style} {_format_style(expected_value)}, "
                        f"but found {_format_style(match.styles[style])}."
                    )


def _format_style(value: Any) -> str:
    if isinstance(value, list) and value and all(item == value[0] for item in value):
        return str(value[0])
    return str(value)
