"""A student file with the same name as a helper module gets a message asking them to rename it."""

import pytest

from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.fixture import WorkspaceFixture

autograder_config = ConfigObject(workspace_mode=True, workspace_exec_entry="main.py", helper_modules=["helper_function"])


@pytest.mark.grading_data(name="query", points=1)
def test_query(workspace_sandbox: WorkspaceFixture) -> None:
    assert workspace_sandbox.query("VALUE") == 1
