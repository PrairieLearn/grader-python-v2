"""Runs docker/run.sh against a temporary job directory, with the layout PrairieLearn creates."""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

RUN_SH = Path(__file__).parents[1] / "docker" / "run.sh"

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="run.sh only runs on Unix systems")

TEST_FILE = """
from pytest_prairielearn_grader.fixture import DataFixture, StudentFixture


def test_params(sandbox: StudentFixture, data_json: DataFixture) -> None:
    assert data_json["params"]["expected"] == 42
    assert sandbox.query("ANSWER") == 42
    assert sandbox.query_setup("from_setup") == 42
"""

SETUP_CODE = """
from_setup = __data_params["expected"]
"""

# Stands in for `uv run`, and drops the option that needs root and an 'ag' user.
FAKE_UV = f"""#!{sys.executable}
import os
import sys

args = sys.argv[2:]
index = args.index("--worker-username")
del args[index : index + 2]
os.execv(sys.executable, [sys.executable, "-m", *args])
"""


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


@pytest.fixture
def job_dir(tmp_path: Path) -> Path:
    job = tmp_path / "grade"
    (job / "tests").mkdir(parents=True)
    (job / "student").mkdir()
    (job / "tests" / "test_student.py").write_text(TEST_FILE)
    (job / "tests" / "setup_code.py").write_text(SETUP_CODE)
    (job / "student" / "student_code.py").write_text("ANSWER = 42\n")
    return job


def write_data_json(job: Path, content: str) -> Path:
    data_file = job / "data" / "data.json"
    data_file.parent.mkdir()
    data_file.write_text(content)
    data_file.chmod(0o644)
    return data_file


def run_grader(job: Path, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_uv = bin_dir / "uv"
    fake_uv.write_text(FAKE_UV)
    fake_uv.chmod(0o755)
    env = {**os.environ, "JOB_DIR": str(job), "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    return subprocess.run(["/bin/sh", str(RUN_SH)], env=env, capture_output=True, text=True, check=False)


def test_data_json_reaches_grader_and_sandbox(job_dir: Path, tmp_path: Path) -> None:
    content = json.dumps({"params": {"expected": 42}, "correct_answers": {"x": 1}})
    write_data_json(job_dir, content)

    run_grader(job_dir, tmp_path)

    assert json.loads((job_dir / "results" / "results.json").read_text())["score"] == 1.0
    assert (job_dir / "run" / "test_student" / "data.json").read_text() == content


def test_data_json_copies_are_owner_only(job_dir: Path, tmp_path: Path) -> None:
    data_file = write_data_json(job_dir, json.dumps({"params": {"expected": 42}}))

    run_grader(job_dir, tmp_path)

    assert mode(job_dir / "run" / "test_student" / "data.json") == 0o600
    assert mode(data_file) == 0o600
    assert mode(data_file.parent) == 0o700


def test_prairielearn_data_json_replaces_one_from_tests(job_dir: Path, tmp_path: Path) -> None:
    stale = job_dir / "tests" / "data.json"
    stale.write_text(json.dumps({"params": {"expected": 0}}))
    stale.chmod(0o644)
    write_data_json(job_dir, json.dumps({"params": {"expected": 42}}))

    run_grader(job_dir, tmp_path)

    delivered = job_dir / "run" / "test_student" / "data.json"
    assert json.loads(delivered.read_text())["params"]["expected"] == 42
    assert mode(delivered) == 0o600


def test_missing_data_json_still_grades(job_dir: Path, tmp_path: Path) -> None:
    (job_dir / "tests" / "test_student.py").write_text("def test_runs() -> None:\n    assert True\n")
    (job_dir / "tests" / "setup_code.py").unlink()

    run_grader(job_dir, tmp_path)

    assert json.loads((job_dir / "results" / "results.json").read_text())["score"] == 1.0
    assert not (job_dir / "run" / "test_student" / "data.json").exists()
