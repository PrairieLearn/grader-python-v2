import json
import textwrap
from typing import Any

import pytest

pytest_plugins = ("pytester",)

# A list far larger than the OS pipe buffer (~64 KiB) once serialized, so a response and an argument
# each span many underlying reads/writes. The socket transport this replaced capped a request at
# 10 MB; the pipe has no such cap, so this also guards the multi-chunk framing in both directions.
STUDENT_CODE = """
big_list = list(range(200_000))


def sum_values(values):
    return sum(values)
"""

TEST_HEADER = """
import pytest
"""


def run_grader(pytester: pytest.Pytester, tests: str) -> dict[str, dict[str, Any]]:
    pytester.path.joinpath("test_grader.py").write_text(TEST_HEADER + textwrap.dedent(tests))
    pytester.mkdir("test_grader").joinpath("student_code.py").write_text(STUDENT_CODE)
    pytester.runpytest("test_grader.py")
    results = json.loads(pytester.path.joinpath("autograder_results.json").read_text())
    return {result["name"]: result for result in results["tests"]}


def test_large_value_and_argument_round_trip(pytester: pytest.Pytester) -> None:
    result = run_grader(
        pytester,
        """
        @pytest.mark.grading_data(name="case", points=1)
        def test_case(sandbox):
            big = sandbox.query("big_list")
            assert big == list(range(200_000))
            assert sandbox.query_function("sum_values", big) == sum(range(200_000))
        """,
    )["case"]

    assert result["points_frac"] == 1
    assert result["outcome"] == "passed"
