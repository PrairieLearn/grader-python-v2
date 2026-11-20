import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from typing import cast

import numpy as np
import pandas as pd
import pytest
import scipy.sparse as sp
import tomllib

from pytest_prairielearn_grader.json_utils import from_json
from pytest_prairielearn_grader.json_utils import from_server_json
from pytest_prairielearn_grader.json_utils import to_json
from pytest_prairielearn_grader.utils import deserialize_object_unsafe
from pytest_prairielearn_grader.utils import serialize_object_unsafe


def test_serialize_numpy_array() -> None:
    # Create a numpy array
    arr = np.array([1, 2, 3, 4, 5])

    # Serialize the numpy array
    serialized = serialize_object_unsafe(arr)

    # Deserialize the numpy array
    deserialized = cast(np.typing.ArrayLike, deserialize_object_unsafe(serialized))

    # Check if the original and deserialized arrays are equal
    assert np.array_equal(arr, deserialized)


@pytest.mark.parametrize("obj", [np.bool(True), np.int32(42), np.float64(3.14), complex(1, 2), True])
def test_serialize_json(obj: Any) -> None:
    # Serialize the object to JSON-compatible format
    json_compatible = to_json(obj)

    # Deserialize back to original object
    deserialized = from_json(json_compatible)

    np.testing.assert_equal(obj, deserialized)


@pytest.mark.parametrize(
    ("obj", "expected_result"),
    [
        (
            {
                "_type": "ndarray",
                "_value": [
                    [0.6838187162381367, 0.9687669728013233, 0.8739536562117622],
                    [0.6863101440077359, 0.18857604228294678, 0.036780253047014266],
                    [0.3518597494339264, 0.5156619713512136, 0.1474092805728887],
                ],
                "_dtype": "float64",
            },
            np.array([[0.68381872, 0.96876697, 0.87395366], [0.68631014, 0.18857604, 0.03678025], [0.35185975, 0.51566197, 0.14740928]]),
        ),
        (
            {"_type": "ndarray", "_value": [[64, 41, 40], [93, 75, 87], [27, 91, 27]], "_dtype": "int64"},
            np.array([[64, 41, 40], [93, 75, 87], [27, 91, 27]]),
        ),
    ],
)
def test_from_server_json_numpy(obj: dict, expected_result: np.ndarray) -> None:
    # Deserialize back to original object
    deserialized = from_server_json(obj)

    # Check if the original and deserialized arrays are equal
    np.testing.assert_allclose(deserialized, expected_result)


@pytest.mark.parametrize(
    ("obj", "expected_result"),
    [
        (
            {
                "_type": "dataframe",
                "_value": {
                    "index": [0, 1, 2, 3, 4],
                    "columns": ["ColA", "ColB", "ColC"],
                    "data": [[6, 98, 76], [91, 43, 6], [89, 46, 81], [48, 3, 19], [43, 31, 73]],
                },
            },
            pd.DataFrame(np.array([[6, 98, 76], [91, 43, 6], [89, 46, 81], [48, 3, 19], [43, 31, 73]]), columns=["ColA", "ColB", "ColC"]),
        )
    ],
)
def test_from_server_json(obj: dict, expected_result: pd.DataFrame) -> None:
    # Deserialize back to original object
    deserialized = from_server_json(obj)

    # Check if the original and deserialized arrays are equal
    pd.testing.assert_frame_equal(deserialized, expected_result)


def test_from_server_json_networkx_graph() -> None:
    graph = from_server_json(
        {
            "_type": "networkx_graph",
            "_value": {
                "directed": False,
                "multigraph": False,
                "graph": {},
                "nodes": [{"id": 1}, {"id": 2}],
                "adjacency": [[{"id": 2}], [{"id": 1}]],
            },
        }
    )

    assert set(graph.nodes) == {1, 2}


_DENSE = np.array([[1.0, 0.0, 2.0], [0.0, 3.0, 0.0], [4.0, 0.0, 5.0]])
_COMPLEX_DENSE = np.array([[1 + 2j, 0], [0, 3 - 1j]])


@pytest.mark.parametrize(
    "matrix",
    [
        sp.csr_matrix(_DENSE),
        sp.csc_matrix(_DENSE),
        sp.coo_matrix(_DENSE),
        sp.csr_array(_DENSE),
        sp.csc_array(_DENSE),
        sp.coo_array(_DENSE),
        sp.csr_matrix(_DENSE.astype(np.int64)),
        sp.csr_matrix(_COMPLEX_DENSE),
    ],
    ids=lambda m: f"{m.format}_{'array' if isinstance(m, sp.sparray) else 'matrix'}_{m.dtype}",
)
def test_sparse_roundtrips_through_json(matrix: Any) -> None:
    # json.dumps/loads exercises the actual sandbox-to-grader boundary, where
    # the value is encoded as a JSON string and decoded on the grader side.
    restored = from_json(json.loads(json.dumps(to_json(matrix))))

    assert sp.issparse(restored)
    assert restored.format == matrix.format
    assert isinstance(restored, sp.sparray) == isinstance(matrix, sp.sparray)
    assert restored.shape == matrix.shape
    assert restored.dtype == matrix.dtype
    np.testing.assert_array_equal(restored.toarray(), matrix.toarray())


def test_sparse_csr_preserves_native_index_arrays() -> None:
    matrix = sp.csr_matrix(_DENSE)
    restored = from_json(json.loads(json.dumps(to_json(matrix))))

    np.testing.assert_array_equal(restored.indices, matrix.indices)
    np.testing.assert_array_equal(restored.indptr, matrix.indptr)
    np.testing.assert_array_equal(restored.data, matrix.data)


def test_sparse_other_format_roundtrips_as_coo() -> None:
    lil = sp.lil_matrix(_DENSE)
    restored = from_json(json.loads(json.dumps(to_json(lil))))

    assert restored.format == "coo"
    np.testing.assert_array_equal(restored.toarray(), lil.toarray())


def test_optional_dependencies_are_declared() -> None:
    project = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())["project"]
    requirements = project["dependencies"]

    assert not any(requirement.startswith("networkx") for requirement in requirements)
    assert "networkx" not in project["optional-dependencies"]


def test_json_utils_loads_without_optional_dependencies() -> None:
    script = """
import builtins
import runpy
from pathlib import Path
import sys

blocked = {"matplotlib", "networkx", "numpy", "pandas", "scipy"}
original_import = builtins.__import__


def block_optional_imports(name, *args, **kwargs):
    if name.split(".", 1)[0] in blocked:
        raise AssertionError(f"Unexpected optional dependency import: {name}")
    return original_import(name, *args, **kwargs)


builtins.__import__ = block_optional_imports
runpy.run_path(Path(sys.argv[1]), run_name="json_utils")
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(Path(__file__).parents[1] / "src/pytest_prairielearn_grader/json_utils.py")],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
