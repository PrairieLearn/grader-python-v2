import pytest

from pytest_prairielearn_grader.assertions import assert_fn_equal
from pytest_prairielearn_grader.fixture import StudentFixture
from pytest_prairielearn_grader.utils import FunctionStatusCode

EXPECTED_MESSAGE = "Function 'returns_thing' returned a value of type Thing, which can't be sent back to the grader"


@pytest.mark.grading_data(name="raw_response", points=1)
def test_raw_response_has_all_fields(sandbox: StudentFixture) -> None:
    response = sandbox.query_function_raw("returns_thing", 1)

    assert response["status"] == FunctionStatusCode.NOT_SERIALIZABLE
    assert response["value"] is None
    assert response["stdout"] == "called returns_thing\n"
    assert response["stderr"] == ""
    assert response["exception_name"] == "TypeError"
    assert response["exception_message"] is not None
    assert EXPECTED_MESSAGE in response["exception_message"]
    assert response["traceback"] is None


@pytest.mark.grading_data(name="other_values", points=1)
@pytest.mark.parametrize("function_name", ["returns_nested_thing", "returns_self_reference"])
def test_other_unserializable_values(sandbox: StudentFixture, function_name: str) -> None:
    assert sandbox.query_function_raw(function_name, 1)["status"] == FunctionStatusCode.NOT_SERIALIZABLE


@pytest.mark.grading_data(name="query_function", points=1)
def test_query_function_has_clear_error(sandbox: StudentFixture) -> None:
    with pytest.raises(RuntimeError, match=EXPECTED_MESSAGE):
        sandbox.query_function("returns_thing", 1)


@pytest.mark.grading_data(name="sandbox_still_works", points=1)
def test_later_queries_still_work(sandbox: StudentFixture) -> None:
    sandbox.query_function_raw("returns_thing", 1)

    assert sandbox.query_function_raw("add_one", 1)["value"] == 2
    assert sandbox.query_function("add_one", 2) == 3
    assert sandbox.query_function_raw("returns_thing", 1)["status"] == FunctionStatusCode.NOT_SERIALIZABLE


@pytest.mark.grading_data(name="assert_fn_equal", points=1)
def test_assert_fn_equal_shows_clear_error(sandbox: StudentFixture) -> None:
    assert_fn_equal(sandbox, "returns_thing", args=(1,), expected=2)
