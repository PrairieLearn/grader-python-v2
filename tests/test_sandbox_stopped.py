import json
import sys

import pytest

pytest_plugins = ("pytester",)

TESTS = """
import pytest

from pytest_prairielearn_grader import ConfigObject

autograder_config = ConfigObject(import_blacklist=[])


@pytest.mark.grading_data(name="first", points=1)
def test_first(module_sandbox):
    module_sandbox.query_function("stop")


@pytest.mark.grading_data(name="second", points=1)
def test_second(module_sandbox):
    module_sandbox.query_function("stop")
"""


@pytest.mark.skipif(sys.platform == "win32", reason="SIGKILL is Unix-only")
@pytest.mark.parametrize(
    ("stop", "message"),
    [
        pytest.param(
            "os.kill(os.getpid(), signal.SIGKILL)",
            "The sandbox running your code was killed, probably because your code used too much memory.",
            id="killed",
        ),
        pytest.param("os._exit(3)", "The sandbox running your code stopped unexpectedly with exit code 3.", id="exit_code"),
    ],
)
def test_stopped_sandbox_is_explained(pytester: pytest.Pytester, stop: str, message: str) -> None:
    pytester.path.joinpath("test_grader.py").write_text(TESTS)
    pytester.mkdir("test_grader").joinpath("student_code.py").write_text(f"import os\nimport signal\n\n\ndef stop():\n    {stop}\n")
    pytester.runpytest("test_grader.py")
    results = json.loads(pytester.path.joinpath("autograder_results.json").read_text())

    for result in results["tests"]:
        assert result["points"] == 0
        assert message in result["message"]
