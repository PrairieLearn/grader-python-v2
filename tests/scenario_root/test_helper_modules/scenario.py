"""Modules named by helper_modules can be imported, and nothing else in the tests folder can."""

import pytest

from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.fixture import StudentFixture

autograder_config = ConfigObject(
    helper_modules=["helper_function", "second_helper"],
    sandbox_timeout=5,
)


@pytest.mark.grading_data(name="setup code", points=1)
def test_setup_code(sandbox: StudentFixture) -> None:
    assert sandbox.query_setup("from_setup") == 6


@pytest.mark.grading_data(name="query", points=1)
def test_query(sandbox: StudentFixture) -> None:
    assert sandbox.query("from_leading") == 9
    assert sandbox.query("from_student") == 12
    assert sandbox.query("from_alias") == 15


@pytest.mark.grading_data(name="query_function", points=1)
def test_query_function(sandbox: StudentFixture) -> None:
    assert sandbox.query_function("import_when_called", 7) == 21


@pytest.mark.grading_data(name="module_sandbox", points=1)
def test_module_sandbox(module_sandbox: StudentFixture) -> None:
    assert module_sandbox.query_function("uses_helper", 2) == 6


@pytest.mark.grading_data(name="one copy of each module", points=1)
def test_one_copy(sandbox: StudentFixture) -> None:
    assert sandbox.query_function("same_module") is True


@pytest.mark.grading_data(name="helper modules can import each other", points=1)
def test_second_helper(sandbox: StudentFixture) -> None:
    assert sandbox.query_function("through_second_helper", 2) == 7


@pytest.mark.grading_data(name="modules that aren't named can't be imported", points=1)
@pytest.mark.parametrize(
    "function_name",
    ["import_ans", "import_setup_code", "import_scenario", "helper_imports_ans"],
)
def test_not_named(sandbox: StudentFixture, function_name: str) -> None:
    response = sandbox.query_function_raw(function_name)
    assert response["status"] == "exception"
    assert response["exception_name"] in ("ModuleNotFoundError", "ImportError")
    assert "No module named" in str(response["exception_message"])
