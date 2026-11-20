"""student_source() on a notebook returns the graded cells' code, not scratch cells."""

import pytest

from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.fixture import StudentFixture

autograder_config = ConfigObject(
    student_code_pattern="student_code.ipynb",
    notebook_cell_tag="#grade",
)


@pytest.mark.grading_data(name="notebook source", points=1)
def test_notebook_source_is_graded_cells(sandbox: StudentFixture) -> None:
    source = sandbox.student_source()
    assert "def solution():" in source
    assert "SHOULD_NOT_APPEAR" not in source
