"""Leading code and a tagged notebook cell both read a data file by relative path."""

import pytest

from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.fixture import StudentFixture

autograder_config = ConfigObject(
    data_files=["edges.txt"],
    student_code_pattern="student_code.ipynb",
    notebook_cell_tag="#grade",
    sandbox_timeout=5,
)


@pytest.mark.grading_data(name="notebook", points=1)
def test_notebook(sandbox: StudentFixture) -> None:
    assert sandbox.query("edge_count") == 6
