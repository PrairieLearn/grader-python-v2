"""
Convert plain matplotlib figures to JSON data and back.

Student code runs in the sandbox, so everything in the JSON data is untrusted. Conversion to JSON
uses an allow-list: a plot containing anything not handled here raises UnsupportedPlotError rather
than losing data. Rebuilding only passes validated strings and numbers to matplotlib.

matplotlib is an optional dependency, so json_utils only imports this module when it's needed.
"""

import io
import math
from typing import Any

import numpy as np
from matplotlib.axes import Axes
from matplotlib.collections import PathCollection
from matplotlib.colors import to_hex
from matplotlib.container import BarContainer
from matplotlib.container import ErrorbarContainer
from matplotlib.container import StemContainer
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

MATPLOTLIB_FIGURE_TYPE = "matplotlib_figure"

_SCALES = frozenset({"linear", "log", "symlog", "logit"})
_LINESTYLES = frozenset({"-", "--", "-.", ":", "None", " ", ""})
_DRAWSTYLES = frozenset({"default", "steps", "steps-pre", "steps-mid", "steps-post"})
_ORIENTATIONS = frozenset({"vertical", "horizontal"})
_AXIS_UNITS = frozenset({"number", "date", "category"})
_MAX_FIGURE_SIZE_INCHES = 1000.0


class UnsupportedPlotError(ValueError):
    """The plot contains something that can't be sent to the grader without losing data."""


def is_plot(value: Any) -> bool:
    return isinstance(value, Axes | Figure)


def plot_to_png(value: Any) -> bytes:
    """Render a Figure, or the figure that an Axes belongs to, as a PNG file."""
    if isinstance(value, Axes):
        value = value.figure
    if not isinstance(value, Figure):
        raise TypeError(f"add_image expects a matplotlib Figure or Axes, or PNG bytes, not {type(value).__name__}")
    buffer = io.BytesIO()
    value.savefig(buffer, format="png")
    return buffer.getvalue()


def plot_to_json(value: Any) -> dict[str, Any]:
    """Return JSON data for a Figure, or for the whole figure that an Axes belongs to."""

    figure: Any = value.figure if isinstance(value, Axes) else value
    if not isinstance(figure, Figure):
        raise UnsupportedPlotError("these axes aren't part of a top-level figure")
    _check_figure(figure)
    width, height = figure.get_size_inches()
    return {
        "_type": MATPLOTLIB_FIGURE_TYPE,
        "_value": {
            "size": [float(width), float(height)],
            "suptitle": figure.get_suptitle(),  # type: ignore[attr-defined]
            "axes": [_axes_to_json(axes) for axes in figure.axes],
        },
    }


def _check_figure(figure: Any) -> None:
    suptitle = figure.get_suptitle()
    extra_texts = [text for text in figure.texts if text.get_text() != suptitle]
    if figure.subfigs:
        raise UnsupportedPlotError("subfigures aren't supported")
    if extra_texts or figure.legends or figure.images or figure.lines or figure.patches or figure.artists:
        raise UnsupportedPlotError("text, legends and other items added directly to a figure aren't supported")


def _check_axes(axes: Any) -> None:
    if axes.name != "rectilinear":
        raise UnsupportedPlotError(f"{axes.name} axes aren't supported")
    if axes.child_axes:
        raise UnsupportedPlotError("inset axes aren't supported")
    if axes.images:
        raise UnsupportedPlotError("images aren't supported")
    if axes.texts:
        raise UnsupportedPlotError("text and annotations aren't supported")
    if axes.tables:
        raise UnsupportedPlotError("tables aren't supported")
    if axes.artists:
        raise UnsupportedPlotError("custom artists aren't supported")

    bar_patches: set[int] = set()
    for container in axes.containers:
        if isinstance(container, ErrorbarContainer):
            raise UnsupportedPlotError("errorbar plots aren't supported")
        if isinstance(container, StemContainer):
            raise UnsupportedPlotError("stem plots aren't supported")
        if not isinstance(container, BarContainer):
            raise UnsupportedPlotError(f"{type(container).__name__} isn't supported")
        if container.errorbar is not None:
            raise UnsupportedPlotError("bars with error bars aren't supported")
        bar_patches.update(id(patch) for patch in container.patches)

    for patch in axes.patches:
        if type(patch) is not Rectangle or id(patch) not in bar_patches:
            raise UnsupportedPlotError(f"{type(patch).__name__} shapes other than bars and histograms aren't supported")
        if patch.get_data_transform() is not axes.transData:
            raise UnsupportedPlotError("bars that don't use data coordinates aren't supported")

    for collection in axes.collections:
        if type(collection) is not PathCollection:
            raise UnsupportedPlotError(f"{type(collection).__name__} plots aren't supported")
        if collection.get_array() is not None:
            raise UnsupportedPlotError("scatter plots colored by a colormap aren't supported")
        # Compare by identity: matplotlib's == treats some other transforms as equal to transData.
        if collection.get_offset_transform() is not axes.transData:
            raise UnsupportedPlotError("scatter plots that don't use data coordinates aren't supported")

    for line in axes.lines:
        if type(line) is not Line2D:
            raise UnsupportedPlotError(f"{type(line).__name__} lines aren't supported")
        if line.get_transform() is not axes.transData:
            raise UnsupportedPlotError("lines that don't use data coordinates, such as axhline and axvline, aren't supported")
        if not isinstance(line.get_marker(), str | None):
            raise UnsupportedPlotError("custom line markers aren't supported")


def _axis_to_json(axis: Any) -> dict[str, Any]:
    scale = axis.get_scale()
    if scale not in _SCALES:
        raise UnsupportedPlotError(f"the {scale} axis scale isn't supported")

    converter = axis.get_converter()
    converter_module = "" if converter is None else type(converter).__module__
    units = "number"
    categories: list[str] = []
    if converter_module == "matplotlib.dates":
        units = "date"
    elif converter_module == "matplotlib.category":
        units = "category"
        mapping = axis.units._mapping
        categories = [str(category) for category in sorted(mapping, key=mapping.__getitem__)]
    elif converter is not None:
        raise UnsupportedPlotError(f"axis units from {type(converter).__name__} aren't supported")

    return {"scale": scale, "label": axis.get_label_text(), "units": units, "categories": categories}


def _floats(values: Any) -> list[float]:
    return np.asarray(values, dtype=float).ravel().tolist()


def _line_to_json(line: Any) -> dict[str, Any]:
    return {
        "x": _floats(line.get_xdata(orig=False)),
        "y": _floats(line.get_ydata(orig=False)),
        "label": str(line.get_label()),
        "color": to_hex(line.get_color(), keep_alpha=True),
        "linewidth": float(line.get_linewidth()),
        "linestyle": line.get_linestyle(),
        "marker": line.get_marker(),
        "drawstyle": line.get_drawstyle(),
    }


def _scatter_to_json(collection: Any) -> dict[str, Any]:
    offsets = collection.get_offsets()
    return {
        "x": _floats(offsets[:, 0]),
        "y": _floats(offsets[:, 1]),
        "sizes": _floats(collection.get_sizes()),
        "colors": [to_hex(color, keep_alpha=True) for color in collection.get_facecolor()],
        "label": str(collection.get_label()),
    }


def _bars_to_json(container: Any) -> dict[str, Any]:
    return {
        "x": _floats([patch.get_x() for patch in container.patches]),
        "y": _floats([patch.get_y() for patch in container.patches]),
        "width": _floats([patch.get_width() for patch in container.patches]),
        "height": _floats([patch.get_height() for patch in container.patches]),
        "colors": [to_hex(patch.get_facecolor(), keep_alpha=True) for patch in container.patches],
        "orientation": container.orientation,
        "label": str(container.get_label()),
    }


def _axes_to_json(axes: Any) -> dict[str, Any]:
    _check_axes(axes)
    legend = axes.get_legend()
    return {
        "position": [float(value) for value in axes.get_position().bounds],
        "x_axis": _axis_to_json(axes.xaxis),
        "y_axis": _axis_to_json(axes.yaxis),
        "title": {location: axes.get_title(loc=location) for location in ("left", "center", "right")},
        "x_limits": [float(value) for value in axes.get_xlim()],
        "y_limits": [float(value) for value in axes.get_ylim()],
        "lines": [_line_to_json(line) for line in axes.lines],
        "scatters": [_scatter_to_json(collection) for collection in axes.collections],
        "bars": [_bars_to_json(container) for container in axes.containers],
        "legend": None
        if legend is None
        else {"title": legend.get_title().get_text(), "labels": [text.get_text() for text in legend.get_texts()]},
    }


def _as_dict(value: Any, name: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise ValueError(f"{name} should be a dictionary")
    return value


def _as_list(value: Any, name: str) -> list[Any]:
    if type(value) is not list:
        raise ValueError(f"{name} should be a list")
    return value


def _as_str(value: Any, name: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{name} should be a string")
    return value


def _as_number(value: Any, name: str) -> float:
    if type(value) not in (int, float):
        raise ValueError(f"{name} should be a number")
    return float(value)


def _as_finite_number(value: Any, name: str) -> float:
    number = _as_number(value, name)
    if not math.isfinite(number):
        raise ValueError(f"{name} should be finite")
    return number


def _as_choice(value: Any, choices: frozenset[str], name: str) -> str:
    if type(value) is not str or value not in choices:
        raise ValueError(f"{name} has an unsupported value")
    return value


def _as_numbers(value: Any, name: str) -> list[float]:
    return [_as_number(item, name) for item in _as_list(value, name)]


def _as_strs(value: Any, name: str) -> list[str]:
    return [_as_str(item, name) for item in _as_list(value, name)]


def _as_finite_numbers(value: Any, length: int, name: str) -> list[float]:
    numbers = [_as_finite_number(item, name) for item in _as_list(value, name)]
    if len(numbers) != length:
        raise ValueError(f"{name} should have {length} values")
    return numbers


def _same_length(name: str, *columns: list[Any]) -> None:
    if len({len(column) for column in columns}) > 1:
        raise ValueError(f"the values in {name} should have the same length")


def _category_values(values: list[float], categories: list[str], name: str) -> list[str]:
    result = []
    for value in values:
        if not value.is_integer() or not 0 <= value < len(categories):
            raise ValueError(f"{name} has a value that isn't one of its categories")
        result.append(categories[int(value)])
    return result


def _apply_axis_units(axis: Any, axis_data: dict[str, Any], categories: list[str]) -> None:
    if axis_data["units"] == "date":
        axis.axis_date()
    elif axis_data["units"] == "category" and categories:
        axis.update_units(categories)


def _add_bars(axes: Any, data: Any) -> None:
    bars = _as_dict(data, "bars")
    x = _as_numbers(bars["x"], "bar x")
    y = _as_numbers(bars["y"], "bar y")
    width = _as_numbers(bars["width"], "bar width")
    height = _as_numbers(bars["height"], "bar height")
    colors = _as_strs(bars["colors"], "bar colors")
    _same_length("bars", x, y, width, height, colors)
    label = _as_str(bars["label"], "bar label")
    if _as_choice(bars["orientation"], _ORIENTATIONS, "bar orientation") == "vertical":
        axes.bar(x, height, width, bottom=y, align="edge", color=colors, label=label)
    else:
        axes.barh(y, width, height, left=x, align="edge", color=colors, label=label)


def _add_scatter(axes: Any, data: Any) -> None:
    scatter = _as_dict(data, "scatter")
    x = _as_numbers(scatter["x"], "scatter x")
    y = _as_numbers(scatter["y"], "scatter y")
    _same_length("scatter", x, y)
    sizes = _as_numbers(scatter["sizes"], "scatter sizes")
    colors = _as_strs(scatter["colors"], "scatter colors")
    axes.scatter(x, y, s=sizes, c=colors if colors else "none", label=_as_str(scatter["label"], "scatter label"))


def _add_line(axes: Any, data: Any, x_categories: list[str], y_categories: list[str]) -> None:
    line = _as_dict(data, "line")
    x: list[Any] = _as_numbers(line["x"], "line x")
    y: list[Any] = _as_numbers(line["y"], "line y")
    _same_length("line", x, y)
    if x_categories:
        x = _category_values(x, x_categories, "line x")
    if y_categories:
        y = _category_values(y, y_categories, "line y")
    marker = line["marker"]
    if marker is not None:
        marker = _as_str(marker, "line marker")
    axes.plot(
        x,
        y,
        label=_as_str(line["label"], "line label"),
        color=_as_str(line["color"], "line color"),
        linewidth=_as_finite_number(line["linewidth"], "line width"),
        linestyle=_as_choice(line["linestyle"], _LINESTYLES, "line style"),
        marker=marker,
        drawstyle=_as_choice(line["drawstyle"], _DRAWSTYLES, "line drawstyle"),
    )


def _add_axes(figure: Any, data: Any) -> None:
    axes_data = _as_dict(data, "axes")
    axes = figure.add_axes(_as_finite_numbers(axes_data["position"], 4, "axes position"))
    x_axis = _as_dict(axes_data["x_axis"], "x axis")
    y_axis = _as_dict(axes_data["y_axis"], "y axis")
    for axis_data in (x_axis, y_axis):
        _as_choice(axis_data["units"], _AXIS_UNITS, "axis units")
        _as_str(axis_data["label"], "axis label")
    x_categories = _as_strs(x_axis["categories"], "x categories")
    y_categories = _as_strs(y_axis["categories"], "y categories")

    axes.set_xscale(_as_choice(x_axis["scale"], _SCALES, "x scale"))
    axes.set_yscale(_as_choice(y_axis["scale"], _SCALES, "y scale"))

    # Bars and scatter offsets are numbers even on a category axis, so add them before setting units.
    # Lines keep their category names, as they do in the student's plot, so add them after.
    for bars in _as_list(axes_data["bars"], "bars"):
        _add_bars(axes, bars)
    for scatter in _as_list(axes_data["scatters"], "scatters"):
        _add_scatter(axes, scatter)
    _apply_axis_units(axes.xaxis, x_axis, x_categories)
    _apply_axis_units(axes.yaxis, y_axis, y_categories)
    for line in _as_list(axes_data["lines"], "lines"):
        _add_line(axes, line, x_categories, y_categories)

    axes.set_xlabel(x_axis["label"])
    axes.set_ylabel(y_axis["label"])
    titles = _as_dict(axes_data["title"], "title")
    for location in ("left", "center", "right"):
        axes.set_title(_as_str(titles[location], "title"), loc=location)
    axes.set_xlim(_as_finite_numbers(axes_data["x_limits"], 2, "x limits"))
    axes.set_ylim(_as_finite_numbers(axes_data["y_limits"], 2, "y limits"))

    legend = axes_data["legend"]
    if legend is not None:
        legend = _as_dict(legend, "legend")
        axes.legend(_as_strs(legend["labels"], "legend labels"), title=_as_str(legend["title"], "legend title"))


def plot_from_json(data: Any) -> Any:
    """Rebuild a Figure from JSON data, raising ValueError if the data is malformed."""

    try:
        figure_data = _as_dict(data, "figure")
        size = _as_finite_numbers(figure_data["size"], 2, "figure size")
        if not all(0 < value <= _MAX_FIGURE_SIZE_INCHES for value in size):
            raise ValueError("figure size is out of range")
        figure: Any = Figure(figsize=(size[0], size[1]))
        figure.suptitle(_as_str(figure_data["suptitle"], "figure title"))
        for axes_data in _as_list(figure_data["axes"], "figure axes"):
            _add_axes(figure, axes_data)
    except (KeyError, TypeError, ValueError, OverflowError) as e:
        raise ValueError(f"variable of type {MATPLOTLIB_FIGURE_TYPE} has invalid data: {e!r}") from e
    return figure
