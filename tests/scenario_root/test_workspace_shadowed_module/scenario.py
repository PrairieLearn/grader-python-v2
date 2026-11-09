"""
A student file or folder named like a module the sandbox has already loaded fails startup with a
message asking the student to rename it, since Python would ignore it and reuse the loaded module.

The student's project has random.py and json/ (both loaded by the sandbox before student code runs)
and calendar.py (not loaded, so it isn't a clash and isn't listed).
"""

import pytest

from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.fixture import WorkspaceFixture

autograder_config = ConfigObject(
    sandbox_timeout=5.0,
    workspace_mode=True,
)


@pytest.mark.grading_data(name="Uses the student's random module", points=1)
def test_uses_random(workspace_sandbox: WorkspaceFixture) -> None:
    assert workspace_sandbox.query("solution.VALUE") == "mine"
