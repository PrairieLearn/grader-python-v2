"""A named module with no file makes a workspace submission ungradable too."""

import pytest

from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.fixture import WorkspaceFixture

autograder_config = ConfigObject(workspace_mode=True, helper_modules=["helper_function"])


@pytest.mark.grading_data(name="query", points=1)
def test_query(workspace_sandbox: WorkspaceFixture) -> None:
    assert workspace_sandbox.query("calculator.VALUE") == 1
