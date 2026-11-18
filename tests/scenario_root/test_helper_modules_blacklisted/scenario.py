"""A named module that's also blacklisted makes the submission ungradable."""

import pytest

from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.fixture import StudentFixture

autograder_config = ConfigObject(helper_modules=["helper_function"], import_blacklist=["helper_function"])


@pytest.mark.grading_data(name="query", points=1)
def test_query(sandbox: StudentFixture) -> None:
    assert sandbox.query("value") == 1
