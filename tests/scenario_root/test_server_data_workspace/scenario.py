import pytest

from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.fixture import WorkspaceFixture

autograder_config = ConfigObject(workspace_mode=True, names_for_user=["x"], sandbox_timeout=5)


@pytest.mark.grading_data(name="setup code", points=1)
def test_setup_code(workspace_sandbox: WorkspaceFixture) -> None:
    assert workspace_sandbox.query("x") == 5


@pytest.mark.grading_data(name="student code", points=1)
def test_student_code(workspace_sandbox: WorkspaceFixture) -> None:
    workspace_sandbox.query_function("reader.read")
