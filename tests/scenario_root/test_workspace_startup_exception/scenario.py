"""An exception raised by the workspace entry file reaches the results with its message."""

import pytest

from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.fixture import WorkspaceFixture

autograder_config = ConfigObject(
    sandbox_timeout=5.0,
    workspace_mode=True,
    workspace_exec_entry="main.py",
)


@pytest.mark.grading_data(name="Entry file raises", points=1)
def test_entry_raises(workspace_sandbox: WorkspaceFixture) -> None:
    workspace_sandbox.query("main.x")
