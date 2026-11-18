"""A blacklisted submodule is blocked however it's imported, and its parent package isn't."""

import pytest

from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.fixture import StudentFixture

autograder_config = ConfigObject(import_blacklist=["matplotlib.pyplot"], sandbox_timeout=30)


@pytest.mark.grading_data(name="blocked", points=1)
@pytest.mark.parametrize("function_name", ["import_pyplot", "from_matplotlib_import_pyplot"])
def test_blocked(sandbox: StudentFixture, function_name: str) -> None:
    response = sandbox.query_function_raw(function_name, query_timeout=30)
    assert response["exception_name"] == "ImportError"
    assert "Module 'matplotlib.pyplot' is blacklisted" in str(response["exception_message"])


@pytest.mark.grading_data(name="allowed", points=1)
@pytest.mark.parametrize(
    ("function_name", "expected"),
    [("import_matplotlib", "matplotlib"), ("from_matplotlib_import_colors", "matplotlib.colors")],
)
def test_allowed(sandbox: StudentFixture, function_name: str, expected: str) -> None:
    assert sandbox.query_function(function_name, query_timeout=30) == expected
