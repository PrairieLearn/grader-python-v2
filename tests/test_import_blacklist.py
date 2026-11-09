"""How import_blacklist entries match the module an import would load."""

import pytest

from pytest_prairielearn_grader._student_code_runner import _find_blacklisted


@pytest.mark.parametrize(
    ("name", "fromlist", "blacklist", "expected"),
    [
        ("os", (), ["os"], "os"),
        ("os.path", (), ["os"], "os.path"),
        ("os", ("path",), ["os"], "os"),
        ("os", ("*",), ["os"], "os"),
        ("osx_helpers", (), ["os"], None),
        ("json", (), ["os"], None),
        ("matplotlib", (), ["matplotlib.pyplot"], None),
        ("matplotlib.pyplot", (), ["matplotlib.pyplot"], "matplotlib.pyplot"),
        ("matplotlib", ("pyplot",), ["matplotlib.pyplot"], "matplotlib.pyplot"),
        ("matplotlib", ("colors", "pyplot"), ["matplotlib.pyplot"], "matplotlib.pyplot"),
        ("matplotlib", ("colors",), ["matplotlib.pyplot"], None),
        ("matplotlib", ("*",), ["matplotlib.pyplot"], None),
        ("matplotlib.pyplot.figure", (), ["matplotlib.pyplot"], "matplotlib.pyplot.figure"),
    ],
)
def test_find_blacklisted(name: str, fromlist: tuple[str, ...], blacklist: list[str], expected: str | None) -> None:
    assert _find_blacklisted(name, fromlist, blacklist) == expected
