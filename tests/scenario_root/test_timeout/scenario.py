import pytest

from pytest_prairielearn_grader.fixture import FeedbackFixture
from pytest_prairielearn_grader.fixture import StudentFixture
from pytest_prairielearn_grader.utils import FunctionStatusCode

# Module-level initialization timeout (used as default when no marker is present)
initialization_timeout = 0.5


@pytest.mark.grading_data(name="initialization_timeout", points=2)
@pytest.mark.sandbox_timeout(0.05)
def test_query(sandbox: StudentFixture) -> None:
    assert sandbox.query("x") == 5


@pytest.mark.grading_data(name="module_level_timeout", points=2)
def test_query_with_module_timeout(sandbox: StudentFixture) -> None:
    """Test that uses module-level initialization_timeout (0.5s) instead of marker."""
    # Student code sleeps 0.1s, module timeout is 0.5s, so this should pass
    assert sandbox.query("x") == 5


@pytest.mark.grading_data(name="marker_overrides_module", points=2)
@pytest.mark.sandbox_timeout(0.08)
def test_marker_overrides_module_timeout(sandbox: StudentFixture) -> None:
    """Test that marker timeout (0.08s) overrides module-level timeout (0.5s)."""
    # Student code sleeps 0.1s, marker timeout is 0.08s (overrides 0.5s module)
    # This should timeout, proving the marker (0.08s) is used instead of module default (0.5s)
    assert sandbox.query("x") == 5


@pytest.mark.grading_data(name="function_timeout", points=2)
@pytest.mark.sandbox_timeout(0.5)
def test_query_slow(sandbox: StudentFixture, feedback: FeedbackFixture) -> None:
    assert sandbox.query("x") == 5
    assert sandbox.query_function("f_fast", 2, y=3, query_timeout=0.2) == 5
    feedback.set_score(0.1)
    assert sandbox.query_function("f_slow", 2, y=3, query_timeout=0.2) == 5


@pytest.mark.grading_data(name="function_timeout", points=2)
@pytest.mark.sandbox_timeout(0.5)
def test_query_fast(sandbox: StudentFixture, feedback: FeedbackFixture) -> None:
    assert sandbox.query("x") == 5
    assert sandbox.query_function("f_fast", 2, y=3, query_timeout=0.5) == 5
    feedback.set_score(0.1)
    assert sandbox.query_function("f_slow", 2, y=3, query_timeout=0.5) == 5


@pytest.mark.grading_data(name="raw_function_timeout", points=2)
def test_raw_function_timeout_preserves_partial_credit(sandbox: StudentFixture, feedback: FeedbackFixture) -> None:
    failures: list[str] = []
    test_values = [2, 3]

    for n in test_values:
        response = sandbox.query_function_raw("f_fast" if n == 2 else "f_slow", n, y=3, query_timeout=0.2 if n == 2 else 0.05)
        if response["status"] == FunctionStatusCode.TIMEOUT:
            failures.append(f"f({n}) timed out: {response['exception_message']}")
            break

        assert response["status"] == FunctionStatusCode.SUCCESS
        assert response["value"] == n + 3

    if failures:
        feedback.add_message("\n".join(failures))
    feedback.set_score_final(0.5 if failures else 1.0)
