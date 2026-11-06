"""Which student files count as clashing with a helper module."""

from pathlib import Path

from pytest_prairielearn_grader.plugin import _find_helper_name_clashes


def test_no_helper_modules(tmp_path: Path) -> None:
    (tmp_path / "helper.py").write_text("x = 1\n")
    assert _find_helper_name_clashes(tmp_path, None) == []


def test_unrelated_file(tmp_path: Path) -> None:
    (tmp_path / "other.py").write_text("x = 1\n")
    assert _find_helper_name_clashes(tmp_path, {"helper": "x = 1\n"}) == []


def test_identical_copy(tmp_path: Path) -> None:
    (tmp_path / "helper.py").write_text("x = 1\n")
    assert _find_helper_name_clashes(tmp_path, {"helper": "x = 1\n"}) == []


def test_different_file(tmp_path: Path) -> None:
    (tmp_path / "helper.py").write_text("x = 2\n")
    assert _find_helper_name_clashes(tmp_path, {"helper": "x = 1\n"}) == ["helper.py"]


def test_file_that_isnt_utf8(tmp_path: Path) -> None:
    (tmp_path / "helper.py").write_bytes(b"\xff")
    assert _find_helper_name_clashes(tmp_path, {"helper": "x = 1\n"}) == ["helper.py"]


def test_folder(tmp_path: Path) -> None:
    (tmp_path / "helper").mkdir()
    assert _find_helper_name_clashes(tmp_path, {"helper": "x = 1\n"}) == ["helper/"]
