"""How import_blacklist entries match the module an import would load."""

import re
import sys
import types

import pytest

from pytest_prairielearn_grader._student_code_runner import _block_blacklisted_functions
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


def test_block_blacklisted_functions(monkeypatch: pytest.MonkeyPatch) -> None:
    module = types.ModuleType("fake_linalg")
    attributes = vars(module)
    attributes.update(inv=lambda matrix: matrix, solve=lambda matrix, vector: vector, EPSILON=1e-8)
    monkeypatch.setitem(sys.modules, "fake_linalg", module)

    _block_blacklisted_functions(["os", "fake_linalg.inv", "fake_linalg.EPSILON", "missing_module.f"])

    with pytest.raises(RuntimeError, match=re.escape("'fake_linalg.inv' is blacklisted and cannot be used.")):
        attributes["inv"]([[1.0]])
    assert attributes["solve"]([[1.0]], [2.0]) == [2.0]
    assert attributes["EPSILON"] == 1e-8
