"""An exception raised while student code starts up reaches the results with its full message."""

import pytest

from pytest_prairielearn_grader.fixture import StudentFixture


@pytest.mark.grading_data(name="Default output level", points=1)
def test_default_level(sandbox: StudentFixture) -> None:
    sandbox.query("x")


@pytest.mark.grading_data(name="Exception name output level", points=1)
@pytest.mark.output(level="none")
def test_name_level(sandbox: StudentFixture) -> None:
    sandbox.query("x")


@pytest.mark.grading_data(name="Traceback output level", points=1)
@pytest.mark.output(level="traceback")
def test_traceback_level(sandbox: StudentFixture) -> None:
    sandbox.query("x")
