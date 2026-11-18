"""The default blacklist also blocks submodules, such as os.path."""

import pytest

from pytest_prairielearn_grader.fixture import StudentFixture


@pytest.mark.grading_data(name="blocked", points=1)
@pytest.mark.parametrize("function_name", ["import_os", "import_os_path", "from_os_import_path"])
def test_blocked(sandbox: StudentFixture, function_name: str) -> None:
    response = sandbox.query_function_raw(function_name)
    assert response["exception_name"] == "ImportError"
    assert "is blacklisted" in str(response["exception_message"])


@pytest.mark.grading_data(name="allowed", points=1)
def test_allowed(sandbox: StudentFixture) -> None:
    assert sandbox.query_function("import_json") == "1"
