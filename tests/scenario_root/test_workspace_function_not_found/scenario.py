import pytest

from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.fixture import WorkspaceFixture
from pytest_prairielearn_grader.utils import FunctionStatusCode

autograder_config = ConfigObject(workspace_mode=True, sandbox_timeout=10.0)


@pytest.mark.grading_data(name="not_found", points=1)
@pytest.mark.parametrize(
    "name",
    [
        "missing_flat_name",
        "calculator.missing_function",
        "no_such_module.function",
        "no_such_package.no_such_module.function",
        "pkg.no_such_module.function",
        "calculator.add_one.function",
    ],
)
def test_missing_names_are_not_found(workspace_sandbox: WorkspaceFixture, name: str) -> None:
    assert workspace_sandbox.query_function_raw(name) == {
        "status": FunctionStatusCode.NOT_FOUND,
        "value": None,
        "stdout": "",
        "stderr": "",
        "exception_name": "NameError",
        "exception_message": f"Function '{name}' wasn't found in the student code",
        "traceback": None,
    }


@pytest.mark.grading_data(name="query_function", points=1)
def test_query_function_raises_clear_error(workspace_sandbox: WorkspaceFixture) -> None:
    with pytest.raises(NameError) as error:
        workspace_sandbox.query_function("calculator.missing_function")
    assert str(error.value) == "Function 'calculator.missing_function' wasn't found in the student code"


@pytest.mark.grading_data(name="exceptions", points=1)
@pytest.mark.parametrize(
    ("name", "exception_name", "message"),
    [
        ("calculator.raises_key_error", "KeyError", "missing_key"),
        ("calculator.raises_import_error", "ImportError", "student import problem"),
        ("calculator.imports_missing_module", "ModuleNotFoundError", "no_such_module_inside_function"),
        ("has_bad_import.function", "ModuleNotFoundError", "no_such_module_in_student_file"),
        ("raises_import_error_on_load.function", "ImportError", "student module problem"),
        ("raises_attribute_error_on_load.function", "AttributeError", "attribute"),
        ("calculator.CONSTANT", "TypeError", "not callable"),
    ],
)
def test_student_errors_stay_exceptions(workspace_sandbox: WorkspaceFixture, name: str, exception_name: str, message: str) -> None:
    response = workspace_sandbox.query_function_raw(name)

    assert response["status"] == FunctionStatusCode.EXCEPTION
    assert response["exception_name"] == exception_name
    assert response["exception_message"] is not None
    assert message in response["exception_message"]


@pytest.mark.grading_data(name="existing_functions", points=1)
def test_existing_functions_still_work(workspace_sandbox: WorkspaceFixture) -> None:
    assert workspace_sandbox.query_function_raw("no_such_module.function")["status"] == FunctionStatusCode.NOT_FOUND
    assert workspace_sandbox.query_function("calculator.add_one", 1) == 2
    assert workspace_sandbox.query_function("pkg.util.double", 2) == 4
