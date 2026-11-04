import builtins

import pytest

from pytest_prairielearn_grader.fixture import StudentFixture


@pytest.mark.grading_data(name="data_values", points=1)
def test_setup_values_ignore_student_changes(sandbox: StudentFixture) -> None:
    assert sandbox.query_setup("value") == 42
    assert not hasattr(builtins, "grader_compromised")


@pytest.mark.grading_data(name="functions", points=1)
def test_setup_functions_are_returned(sandbox: StudentFixture) -> None:
    assert sandbox.query_setup("add_twenty")(10) == 30


@pytest.mark.grading_data(name="function_globals", points=1)
def test_setup_function_globals_exclude_student_values(sandbox: StudentFixture) -> None:
    assert sandbox.query("shared") == "from student"
    assert sandbox.query_setup("read_shared")() == [1, 2, 3]


@pytest.mark.grading_data(name="unserializable", points=1)
def test_unserializable_setup_value_has_clear_error(sandbox: StudentFixture) -> None:
    with pytest.raises(TypeError, match="Setup variable 'unserializable' could not be serialized with dill"):
        sandbox.query_setup("unserializable")


@pytest.mark.grading_data(name="not_found", points=1)
def test_missing_setup_value(sandbox: StudentFixture) -> None:
    with pytest.raises(NameError, match="Query for setup variable 'missing' failed"):
        sandbox.query_setup("missing")
