import builtins

import numpy as np
import pytest

from pytest_prairielearn_grader.fixture import StudentFixture


def assert_grader_not_compromised() -> None:
    assert not hasattr(builtins, "grader_compromised")


@pytest.mark.grading_data(name="json_values", points=1)
def test_json_values_sent_on_demand(sandbox: StudentFixture) -> None:
    assert sandbox.query_setup("value") == 42
    np.testing.assert_array_equal(sandbox.query_setup("array_value"), np.array([1.0, 2.0]))
    assert len(sandbox.query_setup("large_value", query_timeout=10.0)) == 200000


@pytest.mark.grading_data(name="dill_values", points=1)
def test_values_json_would_change_keep_their_types(sandbox: StudentFixture) -> None:
    assert sandbox.query_setup("tuple_value") == (1, 2)
    assert sandbox.query_setup("int_keys_value") == {1: "one"}


@pytest.mark.grading_data(name="functions", points=1)
def test_setup_functions_ignore_student_changes(sandbox: StudentFixture) -> None:
    assert sandbox.query_setup("add_twenty")(10) == 30
    assert_grader_not_compromised()


@pytest.mark.grading_data(name="function_globals", points=1)
def test_setup_function_globals_exclude_student_values(sandbox: StudentFixture) -> None:
    assert sandbox.query("shared") == "from student"
    assert sandbox.query_setup("read_shared")() == [1, 2, 3]


@pytest.mark.grading_data(name="forged_json", points=1)
def test_forged_json_response_cannot_run_code(sandbox: StudentFixture) -> None:
    assert isinstance(sandbox.query_setup("forged_value"), str)
    assert_grader_not_compromised()


@pytest.mark.grading_data(name="replaced_value", points=1)
def test_value_replaced_with_object_has_clear_error(sandbox: StudentFixture) -> None:
    with pytest.raises(TypeError, match="Setup variable 'replaced_value' could not be serialized as JSON"):
        sandbox.query_setup("replaced_value")
    assert_grader_not_compromised()


@pytest.mark.grading_data(name="unserializable", points=1)
def test_unserializable_setup_value_has_clear_error(sandbox: StudentFixture) -> None:
    with pytest.raises(TypeError, match="Setup variable 'unserializable' could not be serialized with dill"):
        sandbox.query_setup("unserializable")


@pytest.mark.grading_data(name="not_found", points=1)
def test_missing_setup_value(sandbox: StudentFixture) -> None:
    with pytest.raises(NameError, match="Query for setup variable 'missing' failed"):
        sandbox.query_setup("missing")
