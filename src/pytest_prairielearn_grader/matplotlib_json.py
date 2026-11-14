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
from matplotlib.text import Annotation
from matplotlib.text import Text

MATPLOTLIB_FIGURE_TYPE = "matplotlib_figure"

_SCALES = frozenset({"linear", "log", "symlog", "logit"})
_LINESTYLES = frozenset({"-", "--", "-.", ":", "None", " ", ""})
_DRAWSTYLES = frozenset({"default", "steps", "steps-pre", "steps-mid", "steps-post"})
_ORIENTATIONS = frozenset({"vertical", "horizontal"})
_AXIS_UNITS = frozenset({"number", "date", "category"})
_TEXT_COORDINATES = frozenset({"data", "axes"})
_ANNOTATION_TEXT_COORDINATES = frozenset({"data", "axes", "offset points"})
_ORIENTATIONS_FOR_LINES = frozenset({"horizontal", "vertical"})
# matplotlib names for the coordinate systems that annotations can use.
_ANNOTATION_COORDINATE_NAMES = {"data": "data", "axes fraction": "axes", "offset points": "offset points"}
_HORIZONTAL_ALIGNMENTS = frozenset({"left", "center", "right"})
_VERTICAL_ALIGNMENTS = frozenset({"top", "bottom", "center", "baseline", "center_baseline"})
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
    for text in axes.texts:
        if type(text) is Annotation:
            _annotation_coordinates(text)
        elif type(text) is Text:
            _text_coordinates(axes, text)
        else:
            raise UnsupportedPlotError(f"{type(text).__name__} text isn't supported")
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
        if line.get_transform() is not axes.transData and reference_line_orientation(axes, line) is None:
            raise UnsupportedPlotError("lines that don't use data coordinates, other than axhline and axvline, aren't supported")
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


def _text_coordinates(axes: Any, text: Any) -> str:
    # Compare by identity, as for scatter offsets.
    transform = text.get_transform()
    if transform is axes.transData:
        return "data"
    if transform is axes.transAxes:
        return "axes"
    raise UnsupportedPlotError("text that doesn't use data or axes coordinates isn't supported")


def _annotation_coordinates(annotation: Any) -> tuple[str, str]:
    point = _ANNOTATION_COORDINATE_NAMES.get(annotation.xycoords) if isinstance(annotation.xycoords, str) else None
    text = _ANNOTATION_COORDINATE_NAMES.get(annotation.anncoords) if isinstance(annotation.anncoords, str) else None
    if point not in _TEXT_COORDINATES or text is None:
        raise UnsupportedPlotError(
            "annotations are supported only with xycoords 'data' or 'axes fraction' and textcoords 'data', 'axes fraction' or 'offset points'"
        )
    return point, text


def reference_line_orientation(axes: Any, line: Any) -> str | None:
    """Return "horizontal" or "vertical" for a line drawn by axhline or axvline, or None."""
    # Compare by identity: these are the transforms that axhline and axvline use.
    transform = line.get_transform()
    if transform is axes.get_yaxis_transform(which="grid"):
        values = np.asarray(line.get_ydata(orig=False), dtype=float)
        orientation = "horizontal"
    elif transform is axes.get_xaxis_transform(which="grid"):
        values = np.asarray(line.get_xdata(orig=False), dtype=float)
        orientation = "vertical"
    else:
        return None
    if values.shape != (2,) or values[0] != values[1]:
        return None
    return orientation


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


def _reference_line_to_json(axes: Any, line: Any) -> dict[str, Any]:
    orientation = reference_line_orientation(axes, line)
    # The value is in data coordinates, and the extent along the line is a fraction of the axes.
    value, extent = (
        (line.get_ydata(orig=False), line.get_xdata()) if orientation == "horizontal" else (line.get_xdata(orig=False), line.get_ydata())
    )
    return {
        "orientation": orientation,
        "value": float(_floats(value)[0]),
        "extent": _floats(extent),
        "label": str(line.get_label()),
        "color": to_hex(line.get_color(), keep_alpha=True),
        "linewidth": float(line.get_linewidth()),
        "linestyle": line.get_linestyle(),
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


def _data_point(axes: Any, point: Any, coordinates: str) -> list[float]:
    if coordinates != "data":
        return _floats(point)
    # Convert category and date positions to numbers.
    return [float(axes.xaxis.convert_units(point[0])), float(axes.yaxis.convert_units(point[1]))]


def _text_to_json(axes: Any, text: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "text": text.get_text(),
        "horizontal_alignment": text.get_horizontalalignment(),
        "vertical_alignment": text.get_verticalalignment(),
        "rotation": float(text.get_rotation()),
    }
    if type(text) is Annotation:
        # Typed as Any because the matplotlib stubs don't include an annotation's xy and arrow_patch.
        annotation: Any = text
        point_coordinates, text_coordinates = _annotation_coordinates(annotation)
        result |= {
            "kind": "annotation",
            "point": _data_point(axes, annotation.xy, point_coordinates),
            "coordinates": point_coordinates,
            "text_position": _data_point(axes, annotation.xyann, text_coordinates),
            "text_coordinates": text_coordinates,
            "arrow": annotation.arrow_patch is not None,
        }
    else:
        coordinates = _text_coordinates(axes, text)
        result |= {"kind": "text", "point": _data_point(axes, text.get_position(), coordinates), "coordinates": coordinates}
    return result


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
        "lines": [_line_to_json(line) for line in axes.lines if line.get_transform() is axes.transData],
        "reference_lines": [_reference_line_to_json(axes, line) for line in axes.lines if line.get_transform() is not axes.transData],
        "scatters": [_scatter_to_json(collection) for collection in axes.collections],
        "bars": [_bars_to_json(container) for container in axes.containers],
        "texts": [_text_to_json(axes, text) for text in axes.texts],
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


_MATPLOTLIB_ANNOTATION_COORDINATES = {name: matplotlib_name for matplotlib_name, name in _ANNOTATION_COORDINATE_NAMES.items()}


def _add_text(axes: Any, data: Any) -> None:
    text = _as_dict(data, "text")
    kind = _as_choice(text["kind"], frozenset({"text", "annotation"}), "text kind")
    coordinates = _as_choice(text["coordinates"], _TEXT_COORDINATES, "text coordinates")
    point = _as_finite_numbers(text["point"], 2, "text position")
    options = {
        "horizontalalignment": _as_choice(text["horizontal_alignment"], _HORIZONTAL_ALIGNMENTS, "text alignment"),
        "verticalalignment": _as_choice(text["vertical_alignment"], _VERTICAL_ALIGNMENTS, "text alignment"),
        "rotation": _as_finite_number(text["rotation"], "text rotation"),
    }
    content = _as_str(text["text"], "text")
    if kind == "text":
        axes.text(*point, content, transform=axes.transData if coordinates == "data" else axes.transAxes, **options)
        return
    text_coordinates = _as_choice(text["text_coordinates"], _ANNOTATION_TEXT_COORDINATES, "annotation text coordinates")
    if type(text["arrow"]) is not bool:
        raise ValueError("annotation arrow should be true or false")
    axes.annotate(
        content,
        xy=point,
        xycoords=_MATPLOTLIB_ANNOTATION_COORDINATES[coordinates],
        xytext=_as_finite_numbers(text["text_position"], 2, "annotation text position"),
        textcoords=_MATPLOTLIB_ANNOTATION_COORDINATES[text_coordinates],
        arrowprops={"arrowstyle": "->"} if text["arrow"] else None,
        **options,
    )


def _add_reference_line(axes: Any, data: Any) -> None:
    line = _as_dict(data, "reference line")
    start, end = _as_finite_numbers(line["extent"], 2, "reference line extent")
    add = (
        axes.axhline
        if _as_choice(line["orientation"], _ORIENTATIONS_FOR_LINES, "reference line orientation") == "horizontal"
        else axes.axvline
    )
    add(
        _as_finite_number(line["value"], "reference line value"),
        start,
        end,
        label=_as_str(line["label"], "reference line label"),
        color=_as_str(line["color"], "reference line color"),
        linewidth=_as_finite_number(line["linewidth"], "reference line width"),
        linestyle=_as_choice(line["linestyle"], _LINESTYLES, "reference line style"),
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
    for line in _as_list(axes_data["reference_lines"], "reference lines"):
        _add_reference_line(axes, line)
    for text in _as_list(axes_data["texts"], "texts"):
        _add_text(axes, text)

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
