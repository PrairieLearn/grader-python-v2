"""A named module with no file makes the submission ungradable, with a message for the instructor."""

import pytest

from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.fixture import StudentFixture

autograder_config = ConfigObject(helper_modules=["helper_function"])


@pytest.mark.grading_data(name="query", points=1)
def test_query(sandbox: StudentFixture) -> None:
    assert sandbox.query("value") == 1
