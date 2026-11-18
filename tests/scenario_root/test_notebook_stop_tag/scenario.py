"""
Notebook stop-tag scenario.

The notebook has three parts, and Part 3 raises ``ValueError``. Tests marked with
``notebook_stop_tag`` run only the cells before the cell that starts with the tag, so
the Part 1 and Part 2 tests still pass. The unmarked test runs every cell and fails.
"""

import pytest

from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.fixture import StudentFixture

autograder_config = ConfigObject(
    student_code_pattern="student_code*.ipynb",
    sandbox_timeout=5.0,
)


@pytest.mark.notebook_stop_tag("# Part 2")
@pytest.mark.grading_data(name="Part 1", points=1)
def test_part_1(sandbox: StudentFixture) -> None:
    assert sandbox.query_function("double", 4) == 8


@pytest.mark.notebook_stop_tag("# Part 3")
class TestPart2:
    @pytest.mark.grading_data(name="Part 2", points=1)
    def test_part_2(self, sandbox: StudentFixture) -> None:
        assert sandbox.query_function("triple", 4) == 12


@pytest.mark.grading_data(name="Whole notebook", points=1)
def test_whole_notebook(sandbox: StudentFixture) -> None:
    assert sandbox.query_function("double", 4) == 8
