import sys

import pytest

if sys.platform == "win32":
    pytest.skip("Privilege dropping is not supported on Windows", allow_module_level=True)

import os
import pwd
from types import SimpleNamespace

from pytest_prairielearn_grader.utils import drop_privileges


def test_drops_supplementary_groups_before_setuid(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(pwd, "getpwnam", lambda name: SimpleNamespace(pw_uid=1000, pw_gid=1000))
    for name in ("setgroups", "setgid", "setegid", "setuid", "seteuid"):
        monkeypatch.setattr(os, name, lambda value, name=name: calls.append((name, value)))

    drop_privileges("ag")

    assert ("setgroups", []) in calls
    order = [name for name, _ in calls]
    assert order.index("setgroups") < order.index("setuid")
    assert order.index("setgroups") < order.index("setgid")
