import pytest

from pytest_prairielearn_grader.fixture import StudentFixture

EXPECTED_MESSAGE = "The sandbox stopped unexpectedly, so later queries won't work: An error occurred: "


class OnlyInTestFile:
    """The sandbox can't import this file, so it can't load an instance as an argument."""


@pytest.mark.grading_data(name="clear_error", points=1)
def test_failure_raises_clear_error(sandbox: StudentFixture) -> None:
    assert sandbox.query("y") == 5

    with pytest.raises(RuntimeError, match=EXPECTED_MESSAGE):
        sandbox.query_function_raw("identity", OnlyInTestFile())


@pytest.mark.grading_data(name="later_queries", points=1)
def test_later_queries_raise_same_error(sandbox: StudentFixture) -> None:
    with pytest.raises(RuntimeError, match=EXPECTED_MESSAGE):
        sandbox.query_function("identity", OnlyInTestFile())

    with pytest.raises(RuntimeError, match=EXPECTED_MESSAGE):
        sandbox.query("y")
    with pytest.raises(RuntimeError, match=EXPECTED_MESSAGE):
        sandbox.query_function("identity", 1)


@pytest.mark.grading_data(name="uncaught", points=1)
def test_uncaught_failure_shows_message(sandbox: StudentFixture) -> None:
    sandbox.query_function("identity", OnlyInTestFile())
