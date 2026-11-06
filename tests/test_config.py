"""Unit tests for ConfigObject validation."""

import pytest

from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.plugin import _calculate_summary_scores

# ---------------------------------------------------------------------------
# Valid configurations
# ---------------------------------------------------------------------------


def test_default_config() -> None:
    config = ConfigObject()
    assert config.workspace_mode is False
    assert config.sandbox_timeout == 1.0
    assert config.student_code_pattern == "student_code*.py"


def test_single_file_mode_full() -> None:
    config = ConfigObject(
        sandbox_timeout=5.0,
        import_whitelist=["math", "numpy"],
        import_blacklist=["requests"],
        builtin_whitelist=["len", "range"],
        names_for_user=["x", "y"],
        student_code_pattern="submission*.py",
        starting_vars={"coeff": 3.14},
    )
    assert config.sandbox_timeout == 5.0
    assert config.import_whitelist == ["math", "numpy"]
    assert config.student_code_pattern == "submission*.py"


def test_workspace_mode_minimal() -> None:
    config = ConfigObject(workspace_mode=True)
    assert config.workspace_mode is True
    assert config.workspace_student_dir is None
    assert config.workspace_exec_entry is None


def test_workspace_mode_with_student_dir() -> None:
    config = ConfigObject(workspace_mode=True, workspace_student_dir="/grade/student")
    assert config.workspace_student_dir == "/grade/student"


def test_workspace_mode_with_exec_entry() -> None:
    config = ConfigObject(workspace_mode=True, workspace_exec_entry="main.py")
    assert config.workspace_exec_entry == "main.py"


def test_workspace_mode_all_workspace_options() -> None:
    config = ConfigObject(
        workspace_mode=True,
        workspace_student_dir="/grade/student",
        workspace_exec_entry="main.py",
        sandbox_timeout=10.0,
        import_whitelist=["math"],
    )
    assert config.workspace_mode is True
    assert config.workspace_exec_entry == "main.py"


# ---------------------------------------------------------------------------
# Cross-mode conflicts
# ---------------------------------------------------------------------------


def test_workspace_student_dir_requires_workspace_mode() -> None:
    with pytest.raises(ValueError, match="workspace_student_dir requires workspace_mode=True"):
        ConfigObject(workspace_student_dir="/grade/student")


def test_workspace_exec_entry_requires_workspace_mode() -> None:
    with pytest.raises(ValueError, match="workspace_exec_entry requires workspace_mode=True"):
        ConfigObject(workspace_exec_entry="main.py")


def test_student_code_pattern_not_allowed_in_workspace_mode() -> None:
    with pytest.raises(ValueError, match="student_code_pattern is not applicable in workspace mode"):
        ConfigObject(workspace_mode=True, student_code_pattern="submission*.py")


def test_both_workspace_fields_without_mode_raises() -> None:
    # Only one error needed; whichever field is validated first will raise
    with pytest.raises(ValueError):
        ConfigObject(workspace_student_dir="/grade/student", workspace_exec_entry="main.py")


# ---------------------------------------------------------------------------
# Existing field validation
# ---------------------------------------------------------------------------


def test_negative_timeout_raises() -> None:
    with pytest.raises(ValueError, match="sandbox_timeout must be positive"):
        ConfigObject(sandbox_timeout=-1.0)


def test_zero_timeout_raises() -> None:
    with pytest.raises(ValueError, match="sandbox_timeout must be positive"):
        ConfigObject(sandbox_timeout=0.0)


def test_empty_import_whitelist_raises() -> None:
    with pytest.raises(ValueError, match="import_whitelist cannot be empty"):
        ConfigObject(import_whitelist=[])


def test_empty_builtin_whitelist_raises() -> None:
    with pytest.raises(ValueError, match="builtin_whitelist cannot be empty"):
        ConfigObject(builtin_whitelist=[])


def test_empty_names_for_user_raises() -> None:
    with pytest.raises(ValueError, match="names_for_user cannot be empty"):
        ConfigObject(names_for_user=[])


def test_blank_student_code_pattern_raises() -> None:
    with pytest.raises(ValueError, match="student_code_pattern must be a non-empty string"):
        ConfigObject(student_code_pattern="   ")


def test_blank_workspace_student_dir_raises() -> None:
    with pytest.raises(ValueError, match="workspace_student_dir must be a non-empty string"):
        ConfigObject(workspace_mode=True, workspace_student_dir="  ")


def test_blank_workspace_exec_entry_raises() -> None:
    with pytest.raises(ValueError, match="workspace_exec_entry must be a non-empty string"):
        ConfigObject(workspace_mode=True, workspace_exec_entry="")


# ---------------------------------------------------------------------------
# Fixture-level mode guards (via pytester)
# ---------------------------------------------------------------------------

pytest_plugins = ("pytester",)


def test_sandbox_fixture_fails_with_workspace_mode(pytester: pytest.Pytester) -> None:
    """Using the 'sandbox' fixture with workspace_mode=True should error immediately."""
    pytester.makepyfile(
        """
        import pytest
        from pytest_prairielearn_grader import ConfigObject
        from pytest_prairielearn_grader.fixture import StudentFixture

        autograder_config = ConfigObject(workspace_mode=True)

        @pytest.mark.grading_data(name="bad test", points=1)
        def test_bad(sandbox: StudentFixture) -> None:
            pass
        """
    )
    result = pytester.runpytest("-p", "prairielearn-grader", "-v")
    result.stdout.fnmatch_lines(["*sandbox fixture cannot be used with workspace_mode=True*"])
    assert result.ret != 0


def test_workspace_sandbox_fixture_fails_without_workspace_mode(pytester: pytest.Pytester) -> None:
    """Using workspace_sandbox with workspace_mode=False should error immediately."""
    pytester.mkdir("student")  # so workspace dir discovery doesn't fail first
    pytester.makepyfile(
        """
        import pytest
        from pytest_prairielearn_grader import ConfigObject
        from pytest_prairielearn_grader.fixture import WorkspaceFixture

        autograder_config = ConfigObject(workspace_mode=False)

        @pytest.mark.grading_data(name="bad test", points=1)
        def test_bad(workspace_sandbox: WorkspaceFixture) -> None:
            pass
        """
    )
    result = pytester.runpytest("-p", "prairielearn-grader", "-v")
    result.stdout.fnmatch_lines(["*workspace_sandbox fixture requires workspace_mode=True*"])
    assert result.ret != 0


def test_module_sandbox_fixture_fails_with_workspace_mode(pytester: pytest.Pytester) -> None:
    """Using module_sandbox with workspace_mode=True should error immediately."""
    pytester.makepyfile(
        """
        import pytest
        from pytest_prairielearn_grader import ConfigObject
        from pytest_prairielearn_grader.fixture import StudentFixture

        autograder_config = ConfigObject(workspace_mode=True)

        @pytest.mark.grading_data(name="bad test", points=1)
        def test_bad(module_sandbox: StudentFixture) -> None:
            pass
        """
    )
    result = pytester.runpytest("-p", "prairielearn-grader", "-v")
    result.stdout.fnmatch_lines(["*module_sandbox fixture cannot be used with workspace_mode=True*"])
    assert result.ret != 0


# ---------------------------------------------------------------------------
# notebook_cell_tag field
# ---------------------------------------------------------------------------


def test_notebook_cell_tag_valid() -> None:
    config = ConfigObject(notebook_cell_tag="#grade")
    assert config.notebook_cell_tag == "#grade"


def test_notebook_cell_tag_none_default() -> None:
    config = ConfigObject()
    assert config.notebook_cell_tag is None


def test_notebook_cell_tag_blank_raises() -> None:
    with pytest.raises(ValueError, match="notebook_cell_tag must be a non-empty string"):
        ConfigObject(notebook_cell_tag="")


def test_notebook_cell_tag_whitespace_raises() -> None:
    with pytest.raises(ValueError, match="notebook_cell_tag must be a non-empty string"):
        ConfigObject(notebook_cell_tag="   ")


def test_notebook_cell_tag_with_workspace_mode_raises() -> None:
    with pytest.raises(ValueError, match="notebook_cell_tag is not supported in workspace mode"):
        ConfigObject(workspace_mode=True, notebook_cell_tag="#grade")


# ---------------------------------------------------------------------------
# output_level field
# ---------------------------------------------------------------------------


def test_output_level_friendly() -> None:
    config = ConfigObject(output_level="friendly")
    assert config.output_level == "friendly"


def test_output_level_none_default() -> None:
    config = ConfigObject()
    assert config.output_level is None


def test_output_level_all_valid_values() -> None:
    for level in ("none", "message", "traceback", "friendly"):
        config = ConfigObject(output_level=level)
        assert config.output_level == level


def test_output_level_invalid_raises() -> None:
    with pytest.raises(ValueError, match="output_level must be one of"):
        ConfigObject(output_level="verbose")  # type: ignore[arg-type]


def test_summary_scores_use_test_point_values() -> None:
    total_score, max_score = _calculate_summary_scores(
        [
            {"points": 1.0, "max_points": 1},
            {"points": 2.0, "max_points": 2},
            {"points": 3.0, "max_points": 3},
        ]
    )

    assert (total_score, max_score) == (6.0, 6)


# ---------------------------------------------------------------------------
# helper_modules field
# ---------------------------------------------------------------------------


def test_helper_modules_default_is_none() -> None:
    assert ConfigObject().helper_modules is None


def test_helper_modules_valid() -> None:
    assert ConfigObject(helper_modules=["helper_function", "_private2"]).helper_modules == ["helper_function", "_private2"]


def test_helper_modules_not_in_params() -> None:
    assert "helper_modules" not in ConfigObject(helper_modules=["helper_function"]).to_dict()


@pytest.mark.parametrize(
    "name",
    ["", " ", "..", "../ans", "a/b", "a\\b", "pkg.mod", "helper.py", "/grade/tests/ans", "1abc", "has space", "class", 5, None],
)
def test_helper_modules_rejects_invalid_names(name: object) -> None:
    with pytest.raises(ValueError, match="helper_modules must contain plain module names"):
        ConfigObject(helper_modules=[name])  # type: ignore[list-item]


def test_helper_modules_must_be_a_list() -> None:
    with pytest.raises(TypeError, match="helper_modules must be a list"):
        ConfigObject(helper_modules="helper_function")  # type: ignore[arg-type]


def test_helper_modules_cannot_be_empty() -> None:
    with pytest.raises(ValueError, match="helper_modules cannot be empty"):
        ConfigObject(helper_modules=[])


def test_helper_modules_in_workspace_mode() -> None:
    config = ConfigObject(workspace_mode=True, helper_modules=["helper_function"])
    assert config.helper_modules == ["helper_function"]
