import json
import textwrap
from typing import Any

import pytest

pytest_plugins = ("pytester",)

STUDENT_CODE = """
import time


def double(x):
    if x == 3:
        return 0
    if x == 4:
        time.sleep(1)
    if x == 6:
        raise ValueError("six is not allowed")
    return 2 * x
"""

TEST_HEADER = """
import pytest

from pytest_prairielearn_grader import assert_fn_equal
from pytest_prairielearn_grader import assert_true
"""


def run_grader(pytester: pytest.Pytester, tests: str) -> dict[str, dict[str, Any]]:
    """Grade STUDENT_CODE with the given tests, and return each test's result by name."""
    pytester.path.joinpath("test_grader.py").write_text(TEST_HEADER + textwrap.dedent(tests))
    pytester.mkdir("test_grader").joinpath("student_code.py").write_text(STUDENT_CODE)
    pytester.runpytest("test_grader.py")
    results = json.loads(pytester.path.joinpath("autograder_results.json").read_text())
    return {result["name"]: result for result in results["tests"]}


@pytest.mark.parametrize(
    ("test_case", "points_frac", "messages"),
    [
        pytest.param(
            """
            def test_case(sandbox, subtests):
                for x in [1, 2]:
                    with subtests.test():
                        assert_fn_equal(sandbox, "double", args=(x,), expected=2 * x)
            """,
            1.0,
            ["2/2 checks passed."],
            id="all_pass",
        ),
        pytest.param(
            """
            def test_case(sandbox, subtests):
                for x in [1, 2, 3]:
                    with subtests.test():
                        assert_fn_equal(sandbox, "double", args=(x,), expected=2 * x)
            """,
            2 / 3,
            ["2/3 checks passed.", "Checking: double(3)"],
            id="fraction",
        ),
        pytest.param(
            """
            def test_case(sandbox, subtests):
                for x in [1, 4, 2, 5]:
                    with subtests.test():
                        assert_fn_equal(sandbox, "double", args=(x,), expected=2 * x, query_timeout=0.2)
            """,
            0.25,
            [
                "1/4 checks passed.",
                "double(4) timed out after 0.2 seconds.",
                "The remaining 2 checks didn't run because double(4) timed out after 0.2 seconds.",
            ],
            id="timeout_stops_remaining",
        ),
        pytest.param(
            """
            def test_case(sandbox, subtests):
                for x in [6, 1]:
                    with subtests.test():
                        assert_fn_equal(sandbox, "double", args=(x,), expected=2 * x)
            """,
            0.5,
            ["double(6) raised ValueError: six is not allowed"],
            id="exception",
        ),
        pytest.param(
            """
            def test_case(sandbox, subtests):
                for x in [1, 2]:
                    with subtests.test():
                        if x == 2:
                            pytest.skip("not checked")
                        assert_fn_equal(sandbox, "double", args=(x,), expected=2 * x)
            """,
            0.5,
            ["1/2 checks passed.", "not checked"],
            id="skipped_counts_as_failed",
        ),
        pytest.param(
            """
            def test_case(sandbox, subtests):
                with subtests.test():
                    assert_fn_equal(sandbox, "double", args=(1,), expected=2)
                assert_true(False, msg="The test body failed.")
            """,
            0.0,
            ["1/1 checks passed.", "The test body failed."],
            id="body_failure",
        ),
        pytest.param(
            """
            def test_case(sandbox, subtests, feedback):
                for x in [1, 3]:
                    with subtests.test():
                        assert_fn_equal(sandbox, "double", args=(x,), expected=2 * x)
                feedback.set_score_final(0.9)
            """,
            0.9,
            ["1/2 checks passed."],
            id="set_score_final",
        ),
        pytest.param(
            """
            def test_case(sandbox, subtests):
                for x in range(10, 18):
                    with subtests.test():
                        assert_fn_equal(sandbox, "double", args=(x,), expected=-1)
            """,
            0.0,
            ["0/8 checks passed.", "...and 3 more checks failed."],
            id="long_output",
        ),
        pytest.param(
            """
            def test_case(sandbox, subtests):
                with subtests.test("first"):
                    assert_true(False, msg="nope")
                with subtests.test("second"):
                    assert_fn_equal(sandbox, "double", args=(3,), expected=6)
            """,
            0.0,
            ["first: nope", "second:\nChecking: double(3)"],
            id="labels",
        ),
        pytest.param(
            """
            def test_case(sandbox, subtests):
                for x, weight in [(1, 1), (2, 2), (3, 1)]:
                    with subtests.test(weight=weight):
                        assert_fn_equal(sandbox, "double", args=(x,), expected=2 * x)
            """,
            3 / 4,
            ["2/3 checks passed.", "Checking: double(3)"],
            id="weights",
        ),
        pytest.param(
            """
            def test_case(sandbox, subtests):
                with subtests.test(weight="heavy"):
                    assert_fn_equal(sandbox, "double", args=(1,), expected=2)
            """,
            0.0,
            ["A subtest's weight must be a non-negative int or float, not"],
            id="invalid_weight",
        ),
        pytest.param(
            """
            def test_case(sandbox, subtests):
                with subtests.test(weight=0):
                    assert_fn_equal(sandbox, "double", args=(1,), expected=2)
            """,
            0.0,
            ["At least one subtest needs a weight greater than 0."],
            id="all_zero_weights",
        ),
    ],
)
def test_subtests_score(pytester: pytest.Pytester, test_case: str, points_frac: float, messages: list[str]) -> None:
    test_case = '@pytest.mark.grading_data(name="case", points=2)\n' + textwrap.dedent(test_case).lstrip()
    result = run_grader(pytester, test_case)["case"]

    assert result["points_frac"] == pytest.approx(points_frac)
    assert result["points"] == pytest.approx(2 * points_frac)
    assert result["outcome"] == ("passed" if points_frac == 1 else "failed")
    for message in messages:
        assert message in result["message"]
    assert "This check didn't run" not in result["message"]


def test_shown_failures_are_capped(pytester: pytest.Pytester) -> None:
    message = run_grader(
        pytester,
        """
        @pytest.mark.grading_data(name="case", points=1)
        def test_case(sandbox, subtests):
            for x in range(10, 18):
                with subtests.test():
                    assert_fn_equal(sandbox, "double", args=(x,), expected=-1)
        """,
    )["case"]["message"]

    assert "Checking: double(14)" in message
    assert "Checking: double(15)" not in message


def test_timeout_stops_later_tests_on_module_sandbox(pytester: pytest.Pytester) -> None:
    results = run_grader(
        pytester,
        """
        @pytest.mark.grading_data(name="first", points=1)
        def test_first(module_sandbox):
            assert_fn_equal(module_sandbox, "double", args=(4,), expected=8, query_timeout=0.2)


        @pytest.mark.grading_data(name="second", points=1)
        def test_second(module_sandbox):
            assert_fn_equal(module_sandbox, "double", args=(1,), expected=2)
        """,
    )

    assert results["first"]["message"] == "double(4) timed out after 0.2 seconds."
    assert results["second"]["message"] == "This check didn't run because double(4) timed out after 0.2 seconds."
    assert results["second"]["points_frac"] == 0


def test_timeout_reported_by_student_process_stops_sandbox(pytester: pytest.Pytester) -> None:
    # The grader waits a second longer than the call's timeout, so the student process's own
    # timeout reply always arrives first.
    result = run_grader(
        pytester,
        """
        class SlowConnection:
            def __init__(self, conn):
                self.conn = conn

            def poll(self, timeout=None):
                return self.conn.poll(timeout + 1 if timeout is not None else None)

            def __getattr__(self, name):
                return getattr(self.conn, name)


        @pytest.mark.grading_data(name="case", points=1)
        def test_case(sandbox, subtests, monkeypatch):
            monkeypatch.setattr(sandbox, "_conn", SlowConnection(sandbox._conn))
            for x in [1, 4, 2, 5]:
                with subtests.test():
                    assert_fn_equal(sandbox, "double", args=(x,), expected=2 * x, query_timeout=0.2)
        """,
    )["case"]

    assert result["points_frac"] == pytest.approx(0.25)
    assert "double(4) timed out after 0.2 seconds." in result["message"]
    assert "The remaining 2 checks didn't run because double(4) timed out after 0.2 seconds." in result["message"]


def test_zero_weight_failure_keeps_full_points(pytester: pytest.Pytester) -> None:
    result = run_grader(
        pytester,
        """
        @pytest.mark.grading_data(name="case", points=1)
        def test_case(sandbox, subtests):
            for x, weight in [(1, 1), (3, 0)]:
                with subtests.test(weight=weight):
                    assert_fn_equal(sandbox, "double", args=(x,), expected=2 * x)
        """,
    )["case"]

    assert result["points_frac"] == 1
    assert result["outcome"] == "failed"
    assert "Checking: double(3)" in result["message"]
