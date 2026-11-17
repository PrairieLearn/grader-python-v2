"""Test that output_level in ConfigObject applies globally without per-test markers."""

import pytest

from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.assertions import assert_equal
from pytest_prairielearn_grader.assertions import assert_fn_equal
from pytest_prairielearn_grader.fixture import StudentFixture

autograder_config = ConfigObject(
    output_level="message",
)


@pytest.mark.grading_data(name="Test add (global message)", points=2)
def test_fn_equal(sandbox: StudentFixture) -> None:
    """Should use the global level without a per-test marker."""
    assert_fn_equal(sandbox, "add", args=(2, 3), expected=5)


@pytest.mark.grading_data(name="Test variable x (global message)", points=1)
def test_equal_variable(sandbox: StudentFixture) -> None:
    """Should use the global level without a per-test marker."""
    value = sandbox.query("x")
    assert_equal(value, 42, description="variable 'x'")
