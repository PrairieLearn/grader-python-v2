import base64

import pytest
from matplotlib.figure import Figure

from pytest_prairielearn_grader.fixture import FeedbackFixture

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def decode(url: str) -> bytes:
    prefix = "data:image/png;base64,"
    assert url.startswith(prefix)
    return base64.b64decode(url.removeprefix(prefix))


def test_add_image_from_figure_and_axes() -> None:
    figure = Figure()
    axes = figure.add_subplot()
    axes.plot([1, 2, 3])
    feedback = FeedbackFixture("test")

    feedback.add_image(figure, label="Figure")
    feedback.add_image(axes)

    images = feedback.to_dict()["images"]
    assert [image.get("label") for image in images] == ["Figure", None]
    assert all(decode(image["url"]).startswith(PNG_SIGNATURE) for image in images)


def test_add_image_from_bytes() -> None:
    feedback = FeedbackFixture("test")
    feedback.add_image(PNG_SIGNATURE + b"rest", label="Raw")
    assert feedback.to_dict()["images"] == [
        {"url": "data:image/png;base64," + base64.b64encode(PNG_SIGNATURE + b"rest").decode(), "label": "Raw"}
    ]


def test_no_images_key_without_images() -> None:
    assert "images" not in FeedbackFixture("test").to_dict()


def test_add_image_rejects_other_values() -> None:
    with pytest.raises(TypeError, match="not str"):
        FeedbackFixture("test").add_image("plot.png")
