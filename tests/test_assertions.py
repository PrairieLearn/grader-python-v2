from typing import Any

import pytest

from pytest_prairielearn_grader.assertions import assert_fn_equal
from pytest_prairielearn_grader.fixture import _SandboxBase


class _Sandbox(_SandboxBase):
    def __init__(self) -> None:
        pass

    def query_function(self, function_name: str, *args: Any, query_timeout: float = 1.0, **kwargs: Any) -> Any:
        assert function_name == "add"
        assert args == (2, 3)
        assert query_timeout == 1.0
        assert not kwargs
        return 4


def test_assert_fn_equal_accepts_description() -> None:
    with pytest.raises(AssertionError, match="Checking: custom description"):
        assert_fn_equal(_Sandbox(), "add", args=(2, 3), expected=5, description="custom description")
