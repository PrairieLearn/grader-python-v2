from typing import Any

import numpy as np
import pandas as pd
import pytest

from pytest_prairielearn_grader._student_code_runner import encode_setup_variables
from pytest_prairielearn_grader.json_utils import from_json
from pytest_prairielearn_grader.json_utils import is_json_transportable
from pytest_prairielearn_grader.json_utils import to_json
from pytest_prairielearn_grader.utils import QueryStatusCode
from pytest_prairielearn_grader.utils import deserialize_object_unsafe


@pytest.mark.parametrize(
    "value",
    [None, True, 1, 1.5, "text", [1, [2]], {"a": {"b": [1]}}, np.array([1, 2]), np.array([1 + 2j]), np.float64(1.5), np.bool_(True)],
)
def test_json_transportable_values_round_trip(value: Any) -> None:
    assert is_json_transportable(value)
    np.testing.assert_equal(from_json(to_json(value)), value)


def test_dataframe_is_json_transportable() -> None:
    value = pd.DataFrame({"a": [1, 2]})
    assert is_json_transportable(value)
    pd.testing.assert_frame_equal(from_json(to_json(value)), value)


class ListSubclass(list):
    pass


@pytest.mark.parametrize(
    "value",
    [
        (1, 2),
        {1, 2},
        {1: "one"},
        [(1, 2)],
        {"a": (1, 2)},
        [np.array([1])],
        ListSubclass(),
        len,
        np.array(["a"]),
        np.array([object()]),
        pd.Series([1]),
    ],
)
def test_values_json_would_change_are_not_transportable(value: Any) -> None:
    assert not is_json_transportable(value)


def test_self_referencing_list_is_not_transportable() -> None:
    value: list[Any] = []
    value.append(value)
    assert not is_json_transportable(value)


def test_snapshot_leaves_out_json_values() -> None:
    def function() -> int:
        return 1

    encoded = encode_setup_variables({"large": list(range(1000)), "params": {"a": 1}, "function": function})

    assert set(encoded) == {"function"}
    assert encoded["function"]["status"] == QueryStatusCode.SUCCESS


def test_snapshot_records_values_dill_cannot_encode() -> None:
    encoded = encode_setup_variables({"generator": (i for i in range(3))})

    assert encoded["generator"]["status"] == QueryStatusCode.NOT_SERIALIZABLE
    assert encoded["generator"]["error"]


def test_function_snapshot_leaves_out_unused_globals() -> None:
    namespace: dict[str, Any] = {"unused": "x" * 1_000_000, "used": 1}
    exec("def function():\n    return used\n", namespace)  # noqa: S102

    encoded = encode_setup_variables({"function": namespace["function"]})

    assert len(encoded["function"]["value_encoded"]) < 10_000
    function = deserialize_object_unsafe(encoded["function"]["value_encoded"])
    assert function() == 1  # type: ignore[operator]
