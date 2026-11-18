"""A blacklisted function is blocked however student code reaches it, and the rest of its module isn't."""

import pytest

from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.fixture import StudentFixture

autograder_config = ConfigObject(import_blacklist=["numpy.linalg.inv"], sandbox_timeout=30)


@pytest.mark.grading_data(name="called", points=1)
@pytest.mark.parametrize("function_name", ["numpy_attribute", "module_alias"])
def test_called(sandbox: StudentFixture, function_name: str) -> None:
    response = sandbox.query_function_raw(function_name, query_timeout=30)
    assert response["exception_name"] == "RuntimeError"
    assert response["exception_message"] == "'numpy.linalg.inv' is blacklisted and cannot be used."


@pytest.mark.grading_data(name="imported", points=1)
def test_imported(sandbox: StudentFixture) -> None:
    response = sandbox.query_function_raw("from_import", query_timeout=30)
    assert response["exception_name"] == "ImportError"
    assert "Module 'numpy.linalg.inv' is blacklisted" in str(response["exception_message"])


@pytest.mark.grading_data(name="allowed", points=1)
def test_allowed(sandbox: StudentFixture) -> None:
    assert sandbox.query_function("other_function", query_timeout=30) == [0.5]
