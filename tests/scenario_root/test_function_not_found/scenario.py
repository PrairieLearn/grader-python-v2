import pytest

from pytest_prairielearn_grader.assertions import assert_fn_approx_equal
from pytest_prairielearn_grader.assertions import assert_fn_equal
from pytest_prairielearn_grader.fixture import StudentFixture
from pytest_prairielearn_grader.utils import FunctionStatusCode
from pytest_prairielearn_grader.utils import GradingOutputLevel

EXPECTED_MESSAGE = "Function 'missing_function' wasn't found in the student code"


@pytest.mark.grading_data(name="raw_response", points=1)
def test_raw_response_has_all_fields(sandbox: StudentFixture) -> None:
    assert sandbox.query_function_raw("missing_function") == {
        "status": FunctionStatusCode.NOT_FOUND,
        "value": None,
        "stdout": "",
        "stderr": "",
        "exception_name": "NameError",
        "exception_message": EXPECTED_MESSAGE,
        "traceback": None,
    }


@pytest.mark.grading_data(name="query_function", points=1)
def test_query_function_raises_clear_error(sandbox: StudentFixture) -> None:
    with pytest.raises(NameError) as error:
        sandbox.query_function("missing_function")
    assert str(error.value) == EXPECTED_MESSAGE


@pytest.mark.grading_data(name="student_errors", points=1)
@pytest.mark.parametrize(
    ("function_name", "exception_name", "message"),
    [
        ("raises_key_error", "KeyError", "'missing_key'"),
        ("raises_key_error_with_function_name", "KeyError", "'missing_function'"),
        ("raises_attribute_error", "AttributeError", "missing_attribute"),
        ("raises_import_error", "ImportError", "student import problem"),
        ("raises_name_error", "NameError", "undefined_variable"),
    ],
)
def test_errors_inside_function_stay_exceptions(sandbox: StudentFixture, function_name: str, exception_name: str, message: str) -> None:
    response = sandbox.query_function_raw(function_name)

    assert response["status"] == FunctionStatusCode.EXCEPTION
    assert response["exception_name"] == exception_name
    assert response["exception_message"] is not None
    assert message in response["exception_message"]
    assert response["traceback"] is not None
    assert "student_code" in response["traceback"]


@pytest.mark.grading_data(name="output_kept", points=1)
def test_output_kept_for_student_errors(sandbox: StudentFixture) -> None:
    assert sandbox.query_function_raw("raises_key_error")["stdout"] == "before the error\n"


@pytest.mark.grading_data(name="not_callable", points=1)
def test_name_that_is_not_callable_stays_an_exception(sandbox: StudentFixture) -> None:
    response = sandbox.query_function_raw("not_callable")

    assert response["status"] == FunctionStatusCode.EXCEPTION
    assert response["exception_name"] == "TypeError"


@pytest.mark.grading_data(name="later_queries", points=1)
def test_later_queries_still_work(sandbox: StudentFixture) -> None:
    assert sandbox.query_function_raw("missing_function")["status"] == FunctionStatusCode.NOT_FOUND
    assert sandbox.query_function("add_one", 1) == 2


@pytest.mark.output(level=GradingOutputLevel.Friendly)
@pytest.mark.grading_data(name="assert_fn_equal", points=1)
def test_assert_fn_equal_shows_clear_message(sandbox: StudentFixture) -> None:
    assert_fn_equal(sandbox, "missing_function", args=(1,), expected=2)


@pytest.mark.output(level=GradingOutputLevel.Friendly)
@pytest.mark.grading_data(name="assert_fn_approx_equal", points=1)
def test_assert_fn_approx_equal_shows_clear_message(sandbox: StudentFixture) -> None:
    assert_fn_approx_equal(sandbox, "missing_function", args=(1,), expected=2.0)
