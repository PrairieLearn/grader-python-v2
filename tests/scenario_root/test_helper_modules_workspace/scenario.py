"""Helper modules in workspace mode, including a student file with the same name as one."""

import pytest

from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.fixture import WorkspaceFixture

autograder_config = ConfigObject(
    workspace_mode=True,
    workspace_exec_entry="main.py",
    helper_modules=["helper_function", "second_helper"],
    # A whitelisted name isn't importable either unless it's named: the folder isn't on the path.
    import_whitelist=["ans"],
    names_for_user=["from_setup"],
    sandbox_timeout=5,
)


@pytest.mark.grading_data(name="setup code", points=1)
def test_setup_code(workspace_sandbox: WorkspaceFixture) -> None:
    assert workspace_sandbox.query("from_setup") == 6


@pytest.mark.grading_data(name="entry point", points=1)
def test_entry_point(workspace_sandbox: WorkspaceFixture) -> None:
    assert workspace_sandbox.query("from_main") == 15


@pytest.mark.grading_data(name="student module", points=1)
def test_student_module(workspace_sandbox: WorkspaceFixture) -> None:
    assert workspace_sandbox.query_function("calculator.triple_it", 2) == 6
    assert workspace_sandbox.query_function("calculator.add_one", 2) == 3


@pytest.mark.grading_data(name="helper module beats student file", points=1)
def test_student_file_with_same_name(workspace_sandbox: WorkspaceFixture) -> None:
    assert workspace_sandbox.query_function("calculator.source") == "instructor"


@pytest.mark.grading_data(name="builtins", points=1)
def test_builtins(workspace_sandbox: WorkspaceFixture) -> None:
    assert workspace_sandbox.query_function("calculator.own_sum", [1, 2]) == 3
    response = workspace_sandbox.query_function_raw("calculator.total", [1, 2])
    assert response["exception_name"] == "NameError"


@pytest.mark.grading_data(name="unnamed file", points=1)
def test_unnamed_file(workspace_sandbox: WorkspaceFixture) -> None:
    response = workspace_sandbox.query_function_raw("calculator.import_ans")
    assert response["exception_name"] == "ModuleNotFoundError"


@pytest.mark.grading_data(name="whitelist", points=1)
def test_whitelist(workspace_sandbox: WorkspaceFixture) -> None:
    response = workspace_sandbox.query_function_raw("calculator.import_json")
    assert response["exception_name"] == "ImportError"


@pytest.mark.grading_data(name="dotted queries search the student's project", points=1)
def test_dotted_queries(workspace_sandbox: WorkspaceFixture) -> None:
    assert workspace_sandbox.query("helper_function.SOURCE") == "student"
    assert workspace_sandbox.query_function_raw("second_helper.add_one", 1)["status"] != "success"
