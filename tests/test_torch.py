"""Tests for PyTorch tensor serialization and assertion helpers.

torch is an optional, heavy dependency, so these tests are skipped when it isn't installed.
"""

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    import torch
else:
    torch = pytest.importorskip("torch")

from pytest_prairielearn_grader.assertions import assert_tensor_allclose
from pytest_prairielearn_grader.assertions import assert_tensor_equal
from pytest_prairielearn_grader.json_utils import from_json
from pytest_prairielearn_grader.json_utils import to_json

# ---------------------------------------------------------------------------
# Serialization round-trips
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tensor",
    [
        torch.tensor([1.0, 2.0, 3.0]),
        torch.tensor([[1, 2], [3, 4]], dtype=torch.int64),
        torch.tensor(3.5),  # 0-dim scalar
        torch.tensor([True, False, True]),
        torch.zeros(0),  # empty
        torch.tensor([1 + 2j, 3 - 4j], dtype=torch.complex64),
    ],
)
def test_tensor_round_trip(tensor: "torch.Tensor") -> None:
    restored = from_json(to_json(tensor))
    assert isinstance(restored, torch.Tensor)
    assert restored.shape == tensor.shape
    assert restored.dtype == tensor.dtype
    assert torch.equal(restored, tensor)


def test_tensor_serialization_detaches_grad_and_device() -> None:
    tensor = torch.tensor([1.0, 2.0], requires_grad=True)
    # Serializing a tensor that tracks gradients must not raise.
    restored = from_json(to_json(tensor))
    assert not restored.requires_grad
    assert torch.equal(restored, tensor.detach())


def test_to_json_ignores_non_tensor_torch_objects() -> None:
    # A torch dtype is in the torch module but isn't a tensor; it should pass through unchanged.
    assert to_json(torch.float32) is torch.float32


# ---------------------------------------------------------------------------
# assert_tensor_allclose
# ---------------------------------------------------------------------------


def test_allclose_passes_within_tolerance() -> None:
    assert_tensor_allclose(torch.tensor([1.0, 2.0]), torch.tensor([1.0 + 1e-9, 2.0]))


def test_allclose_accepts_arrays_and_lists() -> None:
    assert_tensor_allclose([1.0, 2.0, 3.0], torch.tensor([1.0, 2.0, 3.0]))


def test_allclose_ignores_dtype_by_default() -> None:
    assert_tensor_allclose(torch.tensor([1, 2, 3]), torch.tensor([1.0, 2.0, 3.0]))


def test_allclose_check_dtype_rejects_mismatch() -> None:
    with pytest.raises(AssertionError, match="different dtypes"):
        assert_tensor_allclose(torch.tensor([1, 2]), torch.tensor([1.0, 2.0]), check_dtype=True)


def test_allclose_reports_shape_mismatch() -> None:
    with pytest.raises(AssertionError, match="different shapes"):
        assert_tensor_allclose(torch.zeros(3), torch.zeros(4))


def test_allclose_reports_value_mismatch_detail() -> None:
    with pytest.raises(AssertionError, match="max absolute difference"):
        assert_tensor_allclose(torch.tensor([1.0, 2.0]), torch.tensor([1.0, 5.0]))


def test_allclose_description_in_message() -> None:
    with pytest.raises(AssertionError, match="Checking: forward pass"):
        assert_tensor_allclose(torch.zeros(2), torch.ones(2), description="forward pass")


def test_allclose_equal_nan() -> None:
    nan = float("nan")
    assert_tensor_allclose(torch.tensor([nan, 1.0]), torch.tensor([nan, 1.0]))
    with pytest.raises(AssertionError):
        assert_tensor_allclose(torch.tensor([nan, 1.0]), torch.tensor([nan, 1.0]), equal_nan=False)


# ---------------------------------------------------------------------------
# assert_tensor_equal
# ---------------------------------------------------------------------------


def test_equal_passes() -> None:
    assert_tensor_equal(torch.tensor([1, 2, 3]), torch.tensor([1, 2, 3]))


def test_equal_reports_mismatch_count() -> None:
    with pytest.raises(AssertionError, match="2 of 3 elements differ"):
        assert_tensor_equal(torch.tensor([1, 9, 9]), torch.tensor([1, 2, 3]))


def test_equal_shape_mismatch() -> None:
    with pytest.raises(AssertionError, match="different shapes"):
        assert_tensor_equal(torch.tensor([1, 2]), torch.tensor([1, 2, 3]))
