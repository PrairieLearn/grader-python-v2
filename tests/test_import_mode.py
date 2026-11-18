import pytest

pytest_plugins = ("pytester",)

TESTS = """
import pytest


@pytest.mark.grading_data(name="double", points=1)
def test_double(sandbox) -> None:
    assert sandbox.query_function("double", 2) == 4
"""


def make_questions(pytester: pytest.Pytester) -> None:
    """Make two questions whose tests are both in a file named test_student.py."""
    for question in ["first", "second"]:
        tests_dir = pytester.mkdir(question)
        tests_dir.joinpath("test_student.py").write_text(TESTS)
        tests_dir.joinpath("test_student").mkdir()
        tests_dir.joinpath("test_student", "student_code.py").write_text("def double(x):\n    return 2 * x\n")


def test_questions_with_the_same_test_file_name_run_together(pytester: pytest.Pytester) -> None:
    make_questions(pytester)
    pytester.runpytest().assert_outcomes(passed=2)


def test_chosen_import_mode_is_kept(pytester: pytest.Pytester) -> None:
    make_questions(pytester)
    result = pytester.runpytest("--import-mode=prepend")
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*import file mismatch*"])
