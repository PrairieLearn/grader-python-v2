"""Helper modules work with import restrictions set, and follow them as student code does."""

import pytest

from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.fixture import StudentFixture

autograder_config = ConfigObject(
    helper_modules=["helper_function", "blocked_import", "uses_open"],
    # A whitelisted name isn't importable either unless it's named: the folder isn't on the path.
    import_whitelist=["ans"],
    import_blacklist=["math"],
)


@pytest.mark.grading_data(name="helper module isn't whitelisted", points=1)
def test_helper_module(sandbox: StudentFixture) -> None:
    assert sandbox.query("value") == 6


@pytest.mark.grading_data(name="whitelist still applies", points=1)
def test_whitelist(sandbox: StudentFixture) -> None:
    response = sandbox.query_function_raw("import_json")
    assert response["exception_name"] == "ImportError"
    assert response["exception_message"] == "Module 'json' is not allowed to be imported."


@pytest.mark.grading_data(name="blacklist still applies", points=1)
def test_blacklist(sandbox: StudentFixture) -> None:
    response = sandbox.query_function_raw("import_math")
    assert response["exception_name"] == "ImportError"
    assert response["exception_message"] == "Module 'math' is blacklisted and cannot be imported."


@pytest.mark.grading_data(name="whitelisted file in the folder isn't importable", points=1)
def test_whitelisted_file(sandbox: StudentFixture) -> None:
    response = sandbox.query_function_raw("import_ans")
    assert response["exception_name"] == "ModuleNotFoundError"


@pytest.mark.grading_data(name="helper module's imports follow the rules", points=1)
def test_helper_import_rules(sandbox: StudentFixture) -> None:
    response = sandbox.query_function_raw("import_blocked")
    assert response["exception_name"] == "ImportError"
    assert response["exception_message"] == (
        "Helper module 'blocked_import' could not be loaded: ImportError: Module 'math' is blacklisted and cannot be imported."
    )


@pytest.mark.grading_data(name="helper module's builtins follow the rules", points=1)
def test_helper_builtin_rules(sandbox: StudentFixture) -> None:
    response = sandbox.query_function_raw("call_open")
    assert response["exception_name"] == "NameError"
