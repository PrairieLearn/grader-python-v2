"""Reading the student's submitted source to inspect it with ast.

This mirrors the legacy CS357 sparse questions that parse the submission to
check how a result was produced (for example, detecting matrix multiplication).
"""

import ast

import pytest

from pytest_prairielearn_grader.fixture import StudentFixture


@pytest.mark.grading_data(name="source available", points=1)
def test_source_text_is_the_submission(sandbox: StudentFixture) -> None:
    source = sandbox.student_source()
    assert "def combine(a, b):" in source


@pytest.mark.grading_data(name="ast inspection", points=1)
def test_source_can_be_parsed_and_inspected(sandbox: StudentFixture) -> None:
    tree = ast.parse(sandbox.student_source())

    function_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    assert "combine" in function_names

    uses_matmul = any(isinstance(node, ast.BinOp) and isinstance(node.op, ast.MatMult) for node in ast.walk(tree))
    assert uses_matmul
