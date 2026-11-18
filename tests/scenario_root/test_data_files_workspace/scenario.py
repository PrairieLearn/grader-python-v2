"""Student modules in workspace mode read data files by relative path."""

from pathlib import Path

import pytest

from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.fixture import WorkspaceFixture

autograder_config = ConfigObject(workspace_mode=True, data_files=["edges.txt"], sandbox_timeout=5)


@pytest.mark.grading_data(name="relative path", points=1)
def test_relative_path(workspace_sandbox: WorkspaceFixture, tests_dir: Path) -> None:
    expected = sum(float(x) for x in (tests_dir / "edges.txt").read_text().split())
    assert workspace_sandbox.query_function("analysis.edge_total") == expected
