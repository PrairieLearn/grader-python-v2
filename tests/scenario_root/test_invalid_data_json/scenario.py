from pytest_prairielearn_grader.fixture import StudentFixture


def test_query(sandbox: StudentFixture) -> None:
    assert sandbox.query("ANSWER") == 42
