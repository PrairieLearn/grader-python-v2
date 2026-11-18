"""Commonly used builtins are available to student code without a builtin_whitelist."""

import pytest

from pytest_prairielearn_grader.fixture import StudentFixture


@pytest.mark.grading_data(name="common builtins", points=1)
def test_common_builtins(sandbox: StudentFixture) -> None:
    assert sandbox.query_function("common_builtins", [3, 1, 2]) == [
        6,
        True,
        True,
        [2, 1, 3],
        [3, 1],
        3,
        [1, 2, 3],
        "3.14",
        "0b101",
        "'\\xe9'",
        "list",
        True,
    ]


@pytest.mark.grading_data(name="classes", points=1)
def test_classes(sandbox: StudentFixture) -> None:
    assert sandbox.query_function("classes") == ["square!", 0, "circle"]


@pytest.mark.grading_data(name="dangerous builtins stay blocked", points=1)
def test_open_blocked(sandbox: StudentFixture) -> None:
    response = sandbox.query_function_raw("call_open")
    assert response["exception_name"] == "NameError"
