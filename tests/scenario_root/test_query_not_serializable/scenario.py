import pytest

from pytest_prairielearn_grader.assertions import assert_equal
from pytest_prairielearn_grader.fixture import StudentFixture
from pytest_prairielearn_grader.utils import QueryStatusCode

EXPECTED_MESSAGE = "Variable 'x' has a value of type Thing, which can't be sent back to the grader"


@pytest.mark.grading_data(name="raw_response", points=1)
def test_raw_response_has_all_fields(sandbox: StudentFixture) -> None:
    response = sandbox.query_raw("x")

    assert response["status"] == QueryStatusCode.NOT_SERIALIZABLE
    assert response["value"] is None
    assert response["error"] is not None
    assert EXPECTED_MESSAGE in response["error"]


@pytest.mark.grading_data(name="success_response", points=1)
def test_success_response_has_no_error(sandbox: StudentFixture) -> None:
    assert sandbox.query_raw("y") == {"status": QueryStatusCode.SUCCESS, "value": 5, "error": None}


@pytest.mark.grading_data(name="other_values", points=1)
@pytest.mark.parametrize(("name", "type_name"), [("nested", "list"), ("self_reference", "list")])
def test_other_unserializable_values(sandbox: StudentFixture, name: str, type_name: str) -> None:
    with pytest.raises(RuntimeError, match=f"Variable '{name}' has a value of type {type_name}, which can't be sent back to the grader"):
        sandbox.query(name)


@pytest.mark.grading_data(name="query", points=1)
def test_query_has_clear_error(sandbox: StudentFixture) -> None:
    with pytest.raises(RuntimeError, match=EXPECTED_MESSAGE):
        sandbox.query("x")


@pytest.mark.grading_data(name="sandbox_still_works", points=1)
def test_later_queries_still_work(sandbox: StudentFixture) -> None:
    with pytest.raises(RuntimeError, match=EXPECTED_MESSAGE):
        sandbox.query("x")

    assert sandbox.query("y") == 5
    assert sandbox.query_raw("x")["status"] == QueryStatusCode.NOT_SERIALIZABLE
    assert sandbox.query_raw("y")["value"] == 5


@pytest.mark.grading_data(name="not_found", points=1)
def test_missing_variable(sandbox: StudentFixture) -> None:
    assert sandbox.query_raw("missing")["status"] == QueryStatusCode.NOT_FOUND
    with pytest.raises(NameError, match="Query for 'missing' failed"):
        sandbox.query("missing")


@pytest.mark.output(level="friendly")
@pytest.mark.grading_data(name="assert_equal", points=1)
def test_assert_equal_shows_clear_error(sandbox: StudentFixture) -> None:
    assert_equal(sandbox.query("x"), 25, description="x")
