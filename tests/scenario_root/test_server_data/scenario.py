import pytest

from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.fixture import StudentFixture

# The whitelist doesn't need to list the server_data module.
autograder_config = ConfigObject(import_whitelist=["math"])


@pytest.mark.grading_data(name="total", points=1)
def test_total(sandbox: StudentFixture) -> None:
    assert sandbox.query("total") == 25
