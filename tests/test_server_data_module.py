import pytest

from pytest_prairielearn_grader import server_data


def test_params_are_only_set_in_setup_code() -> None:
    with pytest.raises(RuntimeError, match="use the data_json fixture"):
        _ = server_data.params
