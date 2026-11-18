"""
Values that the question's ``server.py`` prepared, for setup code to import.

In setup code::

    from pytest_prairielearn_grader.server_data import from_server_json, params

    np.random.seed(params["seed"])
    A = from_server_json(params["A"])

The sandbox gives setup code its own copy of this module, with ``params`` set to
``data["params"]``. Student code can't import it, and outside the sandbox ``params`` isn't set: in
tests, use the ``data_json`` fixture instead.
"""

from typing import Any

from pytest_prairielearn_grader.json_utils import from_server_json

__all__ = ["from_server_json", "params"]

params: dict[str, Any]


def __getattr__(name: str) -> Any:
    if name == "params":
        raise RuntimeError("pytest_prairielearn_grader.server_data.params is only set in setup code. In tests, use the data_json fixture.")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
