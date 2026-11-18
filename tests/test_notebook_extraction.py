import json
from pathlib import Path

import pytest

from pytest_prairielearn_grader.fixture import _extract_notebook_code

CELLS = ["#grade\na = 1", "scratch = 0", "#grade part 2\nb = 2", "#grade\nc = 3"]


@pytest.fixture
def notebook(tmp_path: Path) -> Path:
    path = tmp_path / "student_code.ipynb"
    cells: list[dict[str, object]] = [
        {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": source} for source in CELLS
    ]
    path.write_text(json.dumps({"cells": cells, "metadata": {}, "nbformat": 4, "nbformat_minor": 4}))
    return path


@pytest.mark.parametrize(
    ("cell_tag", "stop_tag", "expected"),
    [
        (None, None, CELLS),
        (None, "#grade part 2", CELLS[:2]),
        (None, "#part 9", CELLS),
        ("#grade", "#grade part 2", CELLS[:1]),
        ("#grade", "scratch", CELLS[:1]),
    ],
)
def test_stop_tag(notebook: Path, cell_tag: str | None, stop_tag: str | None, expected: list[str]) -> None:
    assert _extract_notebook_code(notebook, cell_tag, stop_tag) == "\n\n".join(expected)
