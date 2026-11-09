"""In workspace mode, libraries can load what they need, and student code is still restricted."""

import pytest

from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.fixture import WorkspaceFixture

# The default blacklist applies, and numpy, matplotlib and statistics all import os or sys.
autograder_config = ConfigObject(workspace_mode=True, sandbox_timeout=60)


@pytest.mark.grading_data(name="libraries", points=1)
def test_libraries(workspace_sandbox: WorkspaceFixture) -> None:
    assert workspace_sandbox.query("analysis.NORM", query_timeout=60) == 5.0
    assert workspace_sandbox.query("analysis.MEAN") == 2
    assert workspace_sandbox.query("analysis.LINES") == 1


@pytest.mark.grading_data(name="student imports", points=1)
@pytest.mark.parametrize("function_name", ["import_os", "import_os_path", "dunder_import_os"])
def test_student_imports(workspace_sandbox: WorkspaceFixture, function_name: str) -> None:
    response = workspace_sandbox.query_function_raw(f"uses_os.{function_name}")
    assert response["exception_name"] == "ImportError"
    assert "is blacklisted" in str(response["exception_message"])
