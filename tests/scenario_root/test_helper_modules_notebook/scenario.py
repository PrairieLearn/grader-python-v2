"""A tagged notebook cell can import a helper module."""

import pytest

from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.fixture import StudentFixture

autograder_config = ConfigObject(
    helper_modules=["helper_function"],
    student_code_pattern="student_code.ipynb",
    notebook_cell_tag="#grade",
)


@pytest.mark.grading_data(name="notebook", points=1)
def test_notebook(sandbox: StudentFixture) -> None:
    assert sandbox.query("value") == 6
