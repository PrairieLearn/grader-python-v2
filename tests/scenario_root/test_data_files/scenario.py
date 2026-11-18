"""Leading code and student code read data files by relative path; tests read them from tests_dir."""

# No numpy here: pytester runs scenarios in this process and unloads their modules, and numpy fails to load twice.
import os
from pathlib import Path

import pytest

from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.fixture import StudentFixture

autograder_config = ConfigObject(data_files=["edges.txt", "data/weights.txt"], sandbox_timeout=5)

# Root can write to read-only files, so the write checks only hold for other users.
RUNNING_AS_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0


@pytest.mark.grading_data(name="relative paths", points=1)
def test_relative_paths(sandbox: StudentFixture, tests_dir: Path) -> None:
    assert sandbox.query("edge_total") == sum(float(x) for x in (tests_dir / "edges.txt").read_text().split())
    assert sandbox.query("weights") == [1.5, 2.5]


@pytest.mark.grading_data(name="copies are read-only", points=1)
def test_copies_read_only(sandbox: StudentFixture, tests_dir: Path) -> None:
    if not RUNNING_AS_ROOT:
        assert sandbox.query("overwrite_error") == "PermissionError"
        assert sandbox.query("create_error") == "PermissionError"
    # The originals are never touched.
    assert (tests_dir / "edges.txt").read_text() == "0 1\n1 2\n2 0\n"


@pytest.mark.grading_data(name="module sandbox", points=1)
def test_module_sandbox(module_sandbox: StudentFixture) -> None:
    assert module_sandbox.query("weights") == [1.5, 2.5]
