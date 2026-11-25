# PyTorch grading

The `prairielearn/grader-python-pytest:torch` image adds a CPU build of PyTorch (plus `torchvision`
and `torchinfo`) on top of the full scientific stack, for grading machine-learning and data-science
questions.

Use it by setting the image in a question's `info.json`:

```json
{
  "externalGradingOptions": {
    "enabled": true,
    "image": "prairielearn/grader-python-pytest:torch",
    "timeout": 60
  }
}
```

The image uses a Debian (glibc) base rather than the Alpine base of the `lite`/`latest` images,
because PyTorch publishes only glibc wheels. Only the CPU build is installed, so the image stays far
smaller than a CUDA image and runs anywhere.

## Baked-in defaults (all overridable)

Importing torch and running a model takes much longer than the grader's usual 1-second budget, so
the image ships more sensible defaults. Every one of these can be overridden per question.

| Setting                   | Image default | How to override                                                    |
| ------------------------- | ------------- | ----------------------------------------------------------------- |
| Sandbox timeout (seconds) | `10`          | Set `sandbox_timeout` in the question's `ConfigObject`            |
| `OMP_NUM_THREADS`         | `1`           | Set the thread count in student/setup code, or override the env   |
| `MKL_NUM_THREADS`         | `1`           | Set the thread count in student/setup code, or override the env   |

The sandbox-timeout default comes from the `PL_GRADER_SANDBOX_TIMEOUT` environment variable, which
the image sets. A question that sets `sandbox_timeout` in its `ConfigObject` always wins:

```python
from pytest_prairielearn_grader import ConfigObject

# This question needs longer than the image's 10s default.
autograder_config = ConfigObject(sandbox_timeout=30.0)
```

Threads are pinned to 1 for reproducible grading within the grader's CPU budget. Raise them in setup
or student code if a question genuinely needs parallelism.

## Comparing tensors

Two assertion helpers produce clean, student-facing messages for tensor comparisons. Both accept
anything `torch.as_tensor` understands (a tensor, a NumPy array, or a nested list) and compare on the
CPU after detaching from autograd.

```python
from pytest_prairielearn_grader.assertions import assert_tensor_allclose, assert_tensor_equal

@pytest.mark.grading_data(name="forward pass", points=5)
def test_forward(sandbox: StudentFixture) -> None:
    output = sandbox.query_function("forward", sample_input)
    assert_tensor_allclose(output, expected_output, rtol=1e-4)
```

- `assert_tensor_allclose(actual, expected, *, rtol, atol, check_dtype=False, equal_nan=True)` — for
  floating-point tensors. Reports shape mismatches, the number of differing elements, and the
  maximum absolute difference.
- `assert_tensor_equal(actual, expected, *, check_dtype=False)` — for integer, boolean, or index
  tensors where exact equality is meaningful.

Student functions may also simply return a `torch.Tensor`; the grader serializes it automatically,
so `sandbox.query_function(...)` returns a tensor you can compare directly.

## Gotchas

- **No dataset downloads.** The grading sandbox has no network access, so
  `torchvision.datasets(..., download=True)` won't work. Ship any dataset the question needs as a
  `data_files` entry and load it from the local path instead.
- **Determinism.** Seed torch (and NumPy/`random`) in `setup_code.py` so grading is reproducible,
  e.g. `torch.manual_seed(0)`.
