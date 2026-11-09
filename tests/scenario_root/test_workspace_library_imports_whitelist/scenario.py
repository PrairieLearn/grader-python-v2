"""With a whitelist, allowed libraries can load their own dependencies, and student code can't."""

import pytest

from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.fixture import WorkspaceFixture

# pandas loads dependencies such as dateutil with direct __import__ calls.
autograder_config = ConfigObject(workspace_mode=True, sandbox_timeout=60, import_whitelist=["numpy", "pandas"])


@pytest.mark.grading_data(name="whitelisted libraries", points=1)
def test_whitelisted_libraries(workspace_sandbox: WorkspaceFixture) -> None:
    assert workspace_sandbox.query("tables.TOTAL", query_timeout=60) == 6


@pytest.mark.grading_data(name="other imports", points=1)
def test_other_imports(workspace_sandbox: WorkspaceFixture) -> None:
    response = workspace_sandbox.query_function_raw("tables.import_statistics")
    assert response["exception_name"] == "ImportError"
    assert "Module 'statistics' is not allowed to be imported." in str(response["exception_message"])
