# Quick Start Guide

This guide shows how to write a PrairieLearn question that's graded with the pytest-based Python
autograder, and then documents the grader's full API. The grader runs in the
`prairielearn/grader-python-pytest` Docker images and is built on the `pytest-prairielearn-grader`
pytest plugin.

Tests are ordinary pytest test functions. Each test gets a fresh sandbox that runs the student's
code, and the test asks the sandbox for the values and functions it wants to check. Student code
never runs in the same process as the tests.

If you're converting a question that uses the legacy `prairielearn/grader-python` image, follow
[converting.md](converting.md) instead.

## Editor Setup

Install the required packages in your Python environment for IDE support (e.g., VS Code with Pylance):

```bash
pip install pytest pytest-prairielearn-grader
```

This enables IDE features like autocomplete, type checking, and inline documentation when writing test cases.

## Your First Question

This section builds a question that asks students to write a function `average(values)`. A
question that's graded by this grader has these files:

```
average/
├── info.json
├── question.html
└── tests/
    ├── initial_code.py     (starter code shown in the file editor)
    └── test_student.py     (the tests)
```

### `info.json`

Set `gradingMethod` to `"External"` and pick a grader image:

```json
{
  "uuid": "...",
  "title": "Average of a list",
  "topic": "Functions",
  "type": "v3",
  "gradingMethod": "External",
  "externalGradingOptions": {
    "enabled": true,
    "image": "prairielearn/grader-python-pytest:lite",
    "timeout": 30
  }
}
```

### Choosing an Image

Two image variants are published. Pick the smallest one that includes what your question needs — a smaller image means faster cold-start pull times and a reduced security surface.

| Tag       | Size (approx.) | Includes                                                                                                                                                        | Best for                                                                                        |
| --------- | -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `:latest` | ~400–500 MB    | Full scientific stack: `numpy`, `pandas`, `scipy`, `matplotlib` + `matplotcheck2`, `seaborn`, `scikit-learn`, `sympy`, `networkx`, `nltk`, `nbformat`, and more | Any course that needs scientific computing, data science, plotting, or Jupyter notebook grading |
| `:lite`   | ~60–80 MB      | Grader core only: `pytest-prairielearn-grader`, `Pygments`, `beautifulsoup4`, `defusedxml`, `requests`                                                          | Introductory CS courses where student code uses only the Python standard library                |

> **Note:** If a student's code imports a package that isn't present in the image (e.g., `numpy` in `:lite`), it will raise an `ImportError` and the test will fail with an exception. Make sure the image you choose contains everything both your test code and the expected student solution require.

Pinned version tags (e.g., `:v1.2.3` and `:v1.2.3-lite`) are also published alongside each release if you need a reproducible build.

### `question.html`

Students write their code in a file editor. The grader looks for a file named `student_code*.py`,
so name the file `student_code.py`, or set [`student_code_pattern`](#configobject-parameters):

```html
<pl-question-panel>
  <p>
    Write a function <code>average(values)</code> that returns the mean of a
    non-empty list of numbers.
  </p>
  <pl-file-editor
    file-name="student_code.py"
    ace-mode="ace/mode/python"
    source-file-name="tests/initial_code.py"
  ></pl-file-editor>
</pl-question-panel>

<pl-submission-panel>
  <pl-external-grader-results></pl-external-grader-results>
  <pl-file-preview></pl-file-preview>
</pl-submission-panel>
```

### `tests/initial_code.py`

The starter code. The grader doesn't read this file, so it's only used by the file editor. Make
sure it parses: a submission with a syntax error is [ungradable](#ungradable-submission-detection),
so an unchanged starter file should run and get 0 points with feedback.

```python
def average(values):
    return 0
```

### `tests/test_student.py`

Each test is a function that takes the `sandbox` fixture, calls the student's code through it, and
checks the result:

```python
import pytest
from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.assertions import assert_fn_approx_equal
from pytest_prairielearn_grader.fixture import StudentFixture

autograder_config = ConfigObject(output_level="friendly")


@pytest.mark.grading_data(name="Average of one number", points=1)
def test_single(sandbox: StudentFixture) -> None:
    assert_fn_approx_equal(sandbox, "average", args=([5],), expected=5)


@pytest.mark.parametrize("values", [[1, 2, 3], [2.5, -1, 0, 7], list(range(100))])
@pytest.mark.grading_data(name="Average of several numbers", points=2)
def test_several(sandbox: StudentFixture, values: list[float]) -> None:
    assert_fn_approx_equal(sandbox, "average", args=(values,), expected=sum(values) / len(values))
```

- `grading_data` sets the name that students see and the test's points. A parametrized test gets
  those points for each parameter.
- `assert_fn_approx_equal` calls `average` in the sandbox and compares the result with a
  tolerance. On a failure, the student sees which call was checked, the expected value and their
  value. See [Checking Answers](#checking-answers) for the other helpers and for checks that hide the
  expected value.
- The `friendly` output level shows students only the assertion's message, without a traceback.
- Expected values are computed in the test. Don't put a reference solution in a file that student
  code can read.

### Testing Locally

The grader image's entrypoint expects PrairieLearn's `/grade` layout. Build it from your question
and a solution, run the image, and read the results:

```bash
mkdir -p grade/tests grade/student grade/data
cp -R average/tests/. grade/tests/
cp solution.py grade/student/student_code.py
echo '{"params": {}}' > grade/data/data.json
docker run --rm -v "$PWD/grade:/grade" prairielearn/grader-python-pytest:lite
cat grade/results/results.json
```

The image moves files around, so make a fresh copy of the layout for each run. Put in
`data.json` whatever `params` your `server.py` and elements would set. Try at least a correct
solution, the unchanged starter code and a wrong answer for each test, and read each test's
`message` in `results.json`.

To run pytest directly while you write tests, install the packages from [Editor Setup](#editor-setup)
and put the files that the grader reads in a folder named after the test file, next to it:

```
tests/
├── test_student.py
└── test_student/
    ├── student_code_correct.py   (each student_code*.py file is graded separately)
    ├── student_code_wrong.py
    ├── setup_code.py             (if the question has one)
    └── data.json                 (if the tests need params)
```

Then run `pytest tests/test_student.py`.

## Where Code Belongs

Besides `test_student.py`, the `tests` folder can hold these files:

| File               | What the grader does with it                                                                                        |
| ------------------ | ------------------------------------------------------------------------------------------------------------------- |
| `setup_code.py`    | Runs in the sandbox before the student's code. See [Giving Values to Student Code](#giving-values-to-student-code). |
| `leading_code.py`  | Prepended to the student's code, in the same namespace.                                                             |
| `trailing_code.py` | Appended to the student's code, in the same namespace.                                                              |
| Helper modules     | Modules that student code can import, when listed in [`helper_modules`](#helper-modules).                           |
| Data files         | Files that student code can read, when listed in [`data_files`](#data-files).                                       |

Keep as much as possible in `test_student.py`, where each test runs on its own and controls its
feedback. Most questions need only `initial_code.py` and `test_student.py`. Put each piece of code
in the first place in this table that works:

| Code                                                              | Where to put it                                                                                                                                                                 |
| ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Expected values and reference solutions                           | The test                                                                                                                                                                        |
| Calls to the student's functions                                  | `sandbox.query_function` or an assertion helper in the test                                                                                                                     |
| Inputs to the student's functions, including random ones          | The test, passed as arguments. Use `@pytest.mark.parametrize` for several inputs.                                                                                               |
| Variables that student code reads and that `server.py` randomizes | `data["params"]` in `server.py`, listed in `names_for_user`. Tests read them from the `data_json` fixture. This works for plain JSON values, not ones stored with `pl.to_json`. |
| Fixed variables that student code reads                           | `starting_vars` in the `ConfigObject`, listed in `names_for_user`                                                                                                               |
| Variables that student code reads and that need Python to build   | `setup_code.py`, such as numpy arrays or values decoded with `__from_server_json`                                                                                               |
| Blocking a library function                                       | [`import_blacklist`](#blocking-functions), such as `["numpy.linalg.inv"]`                                                                                                       |
| Imports or definitions that the student's code relies on          | The starter code, so that the student sees them. Use `helper_modules` for a module the student imports. Use `leading_code.py` only when neither works.                          |

Why:

- **Trailing code runs when the sandbox starts.** If it calls a student function that raises, every
  test fails with the same error, including tests of other functions. When a test calls the function
  with `query_function`, only that test fails, and the message names the function.
- **Setup code runs again for each test**, in the sandbox, with the same restrictions as student
  code. Random values in it change between tests, and errors in it are reported as if the student's
  code failed.
- **Leading code is hidden.** The student's file only works with code they can't see, so it behaves
  differently when they run it in a workspace or on their own computer.
- **Values in `data["params"]`** are the same in every test and match what `question.html` shows,
  and tests can read them without starting a sandbox.

`test_student.py` can't import the other files in `tests/`. Put helper code for the tests in
`test_student.py`, and read data files in tests with the [`tests_dir`](#available-fixtures)
fixture.

## Writing Tests

Tests are pytest test functions in `tests/test_student.py`. They run in the order they appear in
the file. The examples below leave out their imports, which usually are:

```python
import pytest
from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.assertions import assert_equal, assert_fn_equal, assert_true
from pytest_prairielearn_grader.fixture import FeedbackFixture, StudentFixture
```

### Test Markers

The `@pytest.mark.grading_data` decorator sets what PrairieLearn shows for the test:

- `name`: Test name displayed to students
- `points`: Maximum points for the test
- `include_stdout_feedback`: (Optional, default=`True`) Whether to include student code's stdout in feedback

`@pytest.mark.output(level=...)` sets how much of a failure students see. See
[Output Levels](#output-levels).

### Available Fixtures

These fixtures are provided by the `pytest-prairielearn-grader` package:

1. **`sandbox: StudentFixture`**: Runs the setup code and student code in a new sandbox for each
   test. Use it to query variables and call functions from the student's submission.

2. **`module_sandbox: StudentFixture`**: Like `sandbox`, but shares one sandbox across all tests in
   the file. See [Module-Scoped Sandbox](#module-scoped-sandbox).

3. **`feedback: FeedbackFixture`**: Sets partial credit and adds feedback messages. See
   [Partial Credit and Feedback](#partial-credit-and-feedback).

4. **`data_json: dict | None`**: The contents of PrairieLearn's `data.json`, such as
   `data_json["params"]`.

5. **`tests_dir: Path`**: The question's tests folder. Use it to read instructor files in a test,
   for example `np.loadtxt(tests_dir / "pagerank_large.txt")`, instead of building the path from
   `__file__`.

6. **`workspace_sandbox: WorkspaceFixture`**: For multi-file workspace projects. See
   [Workspace Grading](#workspace-grading).

For implementation details, see the [fixture source code](https://github.com/prairielearn/grader-python-v2/blob/main/src/pytest_prairielearn_grader/fixture.py).

### Querying Student Code

The `sandbox` fixture provides methods to interact with student code:

#### 1. Query Variables

```python
value = sandbox.query("variable_name")
```

Retrieves the value of a variable defined in the student code or `setup_code.py`.
Raises a `NameError` if the variable doesn't exist, and a `RuntimeError` with a clear message if its value can't be sent back to the grader. Later queries on the sandbox still work after either error.

**Example:**

```python
@pytest.mark.grading_data(name="Check Variable", points=2)
def test_variable(sandbox: StudentFixture) -> None:
    coefficient = sandbox.query("coefficient")
    assert_true(coefficient > 0, msg="coefficient must be positive")
```

#### 2. Query Functions

```python
result = sandbox.query_function("function_name", arg1, arg2, kwarg1=value1)
```

Calls a function defined in the student code with the given arguments and **returns the value directly**.

- **On success**: Returns the function's return value
- **On error**: Raises a `RuntimeError` with details about the exception
- **If the function doesn't exist**: Raises a `NameError` saying so

**Example:**

```python
@pytest.mark.grading_data(name="Test Function", points=5)
def test_function(sandbox: StudentFixture) -> None:
    result = sandbox.query_function("calculate", 10, 20)
    assert_equal(result, 30, description="calculate(10, 20)")

    result = sandbox.query_function("process", x=5, y=10)
    assert_equal(result, 15, description="process(x=5, y=10)")
```

You don't need to catch these errors: they fail the test with a message saying what went wrong.

Each call has a 1 second timeout by default. See [Function Timeout](#4-function-timeout). When a
test calls a student function many times, use `query_function_raw` and stop after the first
`"timeout"` status, so that a slow function doesn't use up the grading job's time.

**Testing for specific exceptions with `query_function_raw`:**

When you need to verify that student code raises a specific exception (e.g., testing input validation),
use `query_function_raw` to inspect the response directly:

```python
@pytest.mark.grading_data(name="Test Exception Handling", points=3)
def test_raises_value_error(sandbox: StudentFixture, feedback: FeedbackFixture) -> None:
    response = sandbox.query_function_raw("validate_input", -1)

    assert_true(response["status"] == "exception", msg="validate_input(-1) should raise an exception")
    feedback.set_score(0.5)

    assert_equal(response["exception_name"], "ValueError", description="the exception raised by validate_input(-1)")
    feedback.set_score(0.75)

    assert_true(
        "negative" in response["exception_message"].lower(),
        msg="The error message should mention negative values",
    )
    feedback.set_score(1.0)
```

The `query_function_raw` response contains:

- `status`: One of `"success"`, `"exception"`, `"timeout"`, `"not_found"`, or `"not_serializable"`. `"not_found"` means the function doesn't exist, and only the lookup can cause it: an error raised while the function runs, even a `KeyError` or `ImportError`, is `"exception"`. `"not_serializable"` means the function finished, but its return value can't be sent back to the grader. `exception_message` explains this, and later queries on the sandbox still work.
- `value`: The return value (when status is `"success"`)
- `stdout` / `stderr`: Captured output from the function call
- `exception_name`: The exception class name (e.g., `"ValueError"`)
- `exception_message`: The exception message string
- `traceback`: Full traceback string for debugging

#### 3. Get Captured Output

```python
output = sandbox.get_accumulated_stdout()
```

Retrieves stdout captured from student code execution across all function calls.

**Example:**

```python
@pytest.mark.grading_data(name="Test Output", points=2)
def test_output(sandbox: StudentFixture) -> None:
    sandbox.query_function("print_greeting", "Alice")
    output = sandbox.get_accumulated_stdout()
    assert_true("Hello, Alice!" in output, msg="Greeting not found in output")
```

#### 4. Function Timeout

Control execution time for individual function calls:

```python
# Set a 2-second timeout for this specific function call
result = sandbox.query_function("slow_computation", data, query_timeout=2.0)
```

#### 5. Query Setup Variables

```python
x = sandbox.query_setup("x")
```

Retrieves a variable defined by `setup_code.py`, whether or not it's in `names_for_user`. The value
comes from the same sandbox as the student's code, so a random value matches the one the student's
code received.

**Note**: Values sent back from the sandbox must be serializable. Supported types include: `int`, `float`, `str`, `list`, `dict`, `bool`, `None`, numpy arrays, pandas DataFrames,
and matplotlib plots (see [Testing Matplotlib Plots](#testing-matplotlib-plots)).

### Checking Answers

The `pytest_prairielearn_grader.assertions` module has helpers that raise an `AssertionError` with a
structured message:

```
Checking: add(2, 3)
Expected output: 5
Your code output: -1
The expected and actual output do not match.
```

**`assert_equal(actual, expected, *, msg=None, description=None)`**

Compare two values for equality:

```python
assert_equal(sandbox.query("x"), 42, description="variable 'x'")
```

**`assert_approx_equal(actual, expected, *, rtol=1e-5, atol=1e-8, msg=None, description=None)`**

Compare numbers with a tolerance. It's for scalars: see below for arrays.

```python
result = sandbox.query_function("compute_pi")
assert_approx_equal(result, 3.14159, rtol=1e-3, description="compute_pi()")
```

**`assert_fn_equal(sandbox, func_name, *, args=(), kwargs=None, expected, msg=None, description=None, query_timeout=1.0)`**

Call a student function and compare its return value. The description defaults to the call, such as
`add(2, 3)`:

```python
assert_fn_equal(sandbox, "add", args=(2, 3), expected=5)
```

**`assert_fn_approx_equal(sandbox, func_name, *, args=(), kwargs=None, expected, rtol=1e-5, atol=1e-8, msg=None, query_timeout=1.0)`**

Same as `assert_fn_equal`, with a tolerance:

```python
assert_fn_approx_equal(sandbox, "compute_area", args=(3.0,), expected=28.274, rtol=1e-2)
```

**`assert_plot_equal(plot, expected, *, name="your plot", rtol=1e-5, atol=1e-8, ..., msg=None)`**

Compares a student's matplotlib plot with a reference plot. See [Comparing with a Reference Plot](#comparing-with-a-reference-plot).

**`assert_true(condition, *, msg=None)` / `assert_false(condition, *, msg=None)`**

Check a condition, and show only `msg` when it fails:

```python
assert_true(sandbox.query_function("is_valid", data), msg="is_valid() should accept valid input.")
```

#### Hiding Expected Values

The comparison helpers show the expected value, which is fine when the student can see the test's
inputs. For hidden test cases, use `assert_true` with a message that doesn't include the answer.

Don't use a bare `assert` or numpy and pandas testing functions for checks that students see.
pytest rewrites a bare `assert`, so its message includes both values, such as `assert 6 == 12345`.
`np.testing.assert_allclose` and similar include both arrays. Use
`assert_true(np.allclose(...), msg=...)` instead.

For a numpy array, check the type, dtype, shape and values in that order, so that each failure has
a clear message and a wrong shape doesn't reach `np.allclose`:

```python
value = sandbox.query("x")
assert_true(isinstance(value, np.ndarray), msg="x should be a numpy array")
assert_true(np.issubdtype(value.dtype, np.number), msg="x should contain numbers")
assert_true(value.shape == expected.shape, msg=f"x should have shape {expected.shape}")
assert_true(np.allclose(value, expected), msg="x is inaccurate")
```

For a pandas DataFrame, `pandas.testing.assert_frame_equal(expected, df)` works, but its message
shows both frames.

#### Output Levels

The output level sets how much of a failure students see:

| Level         | Shows to student                                              |
| ------------- | ------------------------------------------------------------- |
| `"none"`      | Exception class name only (e.g., `AssertionError`)            |
| `"message"`   | Exception name + first line of message _(default when unset)_ |
| `"traceback"` | Exception name + message + full traceback                     |
| `"friendly"`  | Only the exception message text — no class name, no traceback |

Use `"friendly"` with the assertion helpers. Set it on one test:

```python
@pytest.mark.output(level="friendly")
@pytest.mark.grading_data(name="Test addition", points=5)
def test_add(sandbox: StudentFixture) -> None:
    assert_fn_equal(sandbox, "add", args=(2, 3), expected=5)
```

On every test in a file, with a module-level `pytestmark`:

```python
pytestmark = pytest.mark.output(level="friendly")
```

Or in the `ConfigObject`:

```python
autograder_config = ConfigObject(output_level="friendly")
```

With the `ConfigObject` approach, individual tests can still override it with
`@pytest.mark.output(level="traceback")`. The `"message"` and `"traceback"` levels can help
advanced students, who can learn from reading tracebacks.

### Partial Credit and Feedback

Tests flow linearly, allowing partial credit after certain assertions pass. When an assertion
fails, the student receives the last partial credit value set before the failure.

```python
@pytest.mark.grading_data(name="Multi-step Test", points=10)
def test_with_partial_credit(sandbox: StudentFixture, feedback: FeedbackFixture) -> None:
    # Check basic requirements (worth 30%)
    result = sandbox.query("data_loaded")
    assert_true(result is not None, msg="Data must be loaded")
    feedback.set_score(0.3)

    # Check intermediate computation (worth 60%)
    intermediate = sandbox.query("processed_data")
    assert_true(len(intermediate) > 0, msg="Data processing failed")
    feedback.set_score(0.6)

    # Check final result (worth 100%)
    final = sandbox.query("final_result")
    assert_true(final == expected_value, msg="Final result incorrect")
    feedback.set_score(1.0)

    # Add custom feedback
    feedback.add_message("Excellent work! All steps completed correctly.")
```

**Key Methods**:

- `feedback.set_score(fraction)`: Set partial credit (0.0 to 1.0)
- `feedback.set_score_final(fraction)`: Set final score (prevents further updates)
- `feedback.add_message(msg)`: Add custom feedback message
- `feedback.add_image(image, label=None)`: Show an image with the test's results. See [Showing Plots to Students](#showing-plots-to-students)

### Capturing and Testing Output

Control whether student code output appears in feedback:

```python
@pytest.mark.grading_data(name="With Output", points=2, include_stdout_feedback=True)
def test_with_output(sandbox: StudentFixture) -> None:
    """Student's print statements will appear in feedback."""
    result = sandbox.query_function("process_data")
    # Any print() calls in student code are captured and shown
    assert_equal(result, expected)


@pytest.mark.grading_data(name="Without Output", points=2, include_stdout_feedback=False)
def test_without_output(sandbox: StudentFixture) -> None:
    """Student's print statements will NOT appear in feedback."""
    result = sandbox.query_function("process_data")
    assert_equal(result, expected)


@pytest.mark.grading_data(name="Manual Output Check", points=2)
def test_output_manually(sandbox: StudentFixture) -> None:
    """Manually inspect and test stdout."""
    sandbox.query_function("print_greeting", "Alice")
    output = sandbox.get_accumulated_stdout()
    assert_true("Hello, Alice!" in output, msg="Greeting message not found in output")
```

### Module-Scoped Sandbox

Use `module_sandbox` instead of `sandbox` when you want student code state to persist
across multiple tests:

```python
@pytest.mark.grading_data(name="Initialize", points=1)
def test_initialization(module_sandbox: StudentFixture) -> None:
    """First test initializes state."""
    result = module_sandbox.query_function("initialize_counter")
    assert_equal(result, 0)


@pytest.mark.grading_data(name="Increment 1", points=1)
def test_increment_1(module_sandbox: StudentFixture) -> None:
    """State persists - counter should be 1."""
    result = module_sandbox.query_function("increment_counter")
    assert_equal(result, 1)


@pytest.mark.grading_data(name="Increment 2", points=1)
def test_increment_2(module_sandbox: StudentFixture) -> None:
    """State still persists - counter should be 2."""
    result = module_sandbox.query_function("increment_counter")
    assert_equal(result, 2)
```

**Use Cases for `module_sandbox`**:

- Testing stateful classes or modules
- Expensive initialization that should only run once
- Testing persistent data structures (databases, file systems, etc.)
- Simulating multi-step workflows

**Important**: With `module_sandbox`, student code is loaded once and shared across all tests
in the module. Use regular `sandbox` for independent test execution.

### Testing Matplotlib Plots

Student code can use matplotlib as usual and provide the plot's `Axes` or `Figure`. The test receives a matplotlib `Figure`.

```python
# Student code
import matplotlib.pyplot as plt


def create_plot(data):
    plt.plot(data)
    plt.xlabel("Time")
    plt.ylabel("Value")
    plt.title("Data Visualization")
    return plt.gca()
```

An `Axes` value brings its whole figure, so subplots are never lost: use `figure.axes` in your test to get each one, in the order the student created them.

What's sent to the test:

- **Lines**, with their data, label, color, width, style, marker and draw style. This includes `plot`, `semilogy`, `loglog` and `step`.
- **Scatter points**, with their positions, sizes and colors.
- **Bars and histograms**, with their positions, sizes, colors and orientation.
- **Axes details:** scales, labels, titles, limits, position and legend labels. Twin axes come back as separate axes in `figure.axes`.
- **Figure details:** size and overall title.

Other plot content makes the query fail with a message saying what isn't supported, rather than losing data. This includes `errorbar`, `stem`, `fill_between`, `pie`, `imshow`, `contour`, `vlines` and `hlines`, `axhline` and `axvline`, `axvspan`, text and annotations, colormapped scatter plots, polar axes, inset axes and subfigures.

Some details aren't sent, so don't grade them: grid lines, tick positions and labels, line and marker transparency set separately from color, scatter marker shapes, the base of a log scale, and `symlog` settings. Values are sent as decimal numbers, and dates come back as matplotlib date numbers (use `matplotlib.dates.num2date` to convert them). Categories on a line come back as strings.

Importing matplotlib can take most of the default 1-second sandbox timeout, so set a longer one in plot questions, such as `sandbox_timeout = 15` at the top of the test file.

`matplotlib` is included in the `:latest` image but not in `:lite`.

#### Comparing with a Reference Plot

`assert_plot_equal` checks a student's plot against a reference plot that the test draws itself:

```python
import numpy as np
import pytest
from matplotlib.figure import Figure
from pytest_prairielearn_grader.assertions import assert_plot_equal
from pytest_prairielearn_grader.fixture import StudentFixture
from pytest_prairielearn_grader.utils import GradingOutputLevel


@pytest.mark.output(level=GradingOutputLevel.Friendly)
@pytest.mark.grading_data(name="plot", points=1)
def test_plot(sandbox: StudentFixture) -> None:
    reference = Figure()
    axes = reference.subplots()
    x = np.arange(0, 11)
    axes.semilogy(x, np.exp(x))

    assert_plot_equal(sandbox.query("plot"), reference)
```

Draw the reference on a `Figure` made directly, as here, rather than with `plt`, so that it doesn't
share pyplot's current figure with anything else in the test. Both plots can be a `Figure` or an
`Axes`, and subplots are compared in order.

By default, it checks:

- **Subplots:** the number of axes.
- **Scales:** the x and y axis scales, such as linear or log.
- **Data:** the lines, scatter plots and bar plots, which must have the same number of each kind. Data is compared with `numpy.allclose`, using `rtol` and `atol`.

The series can be in any order, and a line also matches when its points are in reverse order, since
it looks the same. The points in a scatter plot and the bars in a bar plot can be in any order.

Keyword arguments change what's checked:

| Argument       | Default | Checks                                                                                                      |
| -------------- | ------- | ----------------------------------------------------------------------------------------------------------- |
| `check_scales` | `True`  | The x and y axis scales.                                                                                    |
| `check_data`   | `True`  | The data in lines, scatter plots and bar plots.                                                             |
| `ordered`      | `False` | Requires lines, scatter plots, bar plots and legend labels to be in the reference's order.                  |
| `allow_extra`  | `False` | Allows more lines, scatter plots or bar plots than the reference, such as a student's extra reference line. |
| `check_labels` | `False` | The x and y axis labels, exactly.                                                                           |
| `check_titles` | `False` | The title of each subplot and the figure, exactly.                                                          |
| `check_legend` | `False` | The legend's labels and title, or that neither plot has a legend.                                           |
| `check_limits` | `False` | The x and y axis limits, within `rtol` and `atol`.                                                          |
| `check_styles` | `False` | Line colors, styles and markers, scatter point colors, and bar colors.                                      |

A failure describes the first difference found, such as `Expected a log scale on the y-axis of your
plot, but found a linear scale.` or `No line in your plot matches the line labeled 'exp'.` Lines
are named by their labels when the reference has them. Use `name` to call the plot something else
in messages, such as `name="plot"` for a variable, or `msg` to show your own message instead.

#### Checking Plot Properties with matplotcheck

For checks that `assert_plot_equal` doesn't cover, use the `Figure` directly or
[matplotcheck](https://matplotcheck2.readthedocs.io/en/latest/), which is included in the `:latest`
image. Its `PlotTester` can check that a label or title contains a word, histogram bins, the slope
of a fitted line, and more. It can be used in the same test as `assert_plot_equal`:

```python
# Test code
import matplotlib
matplotlib.use("Agg")  # Non-GUI backend for server environments

import pytest
from matplotlib.figure import Figure
from matplotcheck.base import PlotTester
from pytest_prairielearn_grader.assertions import assert_equal, assert_true
from pytest_prairielearn_grader.fixture import StudentFixture


@pytest.mark.grading_data(name="Plot Test", points=5)
def test_student_plot(sandbox: StudentFixture) -> None:
    """Test that student creates a correct plot."""
    # Student function returns an Axes or Figure, which arrives here as a Figure
    plot = sandbox.query_function("create_plot", data)

    assert_true(isinstance(plot, Figure))
    assert_equal(len(plot.axes), 1)

    # Use matplotcheck for detailed plot testing
    ax = plot.axes[0]
    pt = PlotTester(ax)

    # Check plot properties
    pt.assert_plot_type("line")
    pt.assert_axis_label_contains(axis="x", strings_expected=["Time"])
    pt.assert_axis_label_contains(axis="y", strings_expected=["Value"])
    pt.assert_title_contains(["Data Visualization"])
```

#### Showing Plots to Students

To show the student's plot with a test's results, pass it to `feedback.add_image`:

```python
@pytest.mark.grading_data(name="Plot Test", points=5)
def test_student_plot(sandbox: StudentFixture, feedback: FeedbackFixture) -> None:
    plot = sandbox.query_function("create_plot", data)
    feedback.add_image(plot, label="Your plot")
    ...
```

- **Values:** `add_image` takes a matplotlib `Figure` or `Axes`, or the bytes of a PNG file, and
  adds it to the test's `images` in `results.json`. `<pl-external-grader-results>` shows it under
  the test, whether the test passes or fails.
- **Call it first:** a failed assertion ends the test, so add the image before checking the plot.
- **A copy of the plot:** the image is drawn from the `Figure` that the test received, which the
  grader rebuilt from the student's plot. It shows the data, scales, labels and other parts the
  grader copies, but other styling can look different from what the student saw.
- **Size:** PrairieLearn limits the whole `results.json` to 1 MB. A typical plot is tens of
  kilobytes, but don't add an image in every case of a test with many parameters.

The grader automatically serializes/deserializes:

- Matplotlib `Axes` and `Figure` values (received as a `Figure`)
- NumPy arrays
- Pandas DataFrames
- Standard Python types (int, float, str, list, dict, bool, None)

## Giving Values to Student Code

Some questions give students variables to use, such as a matrix to factor. Student code only gets
the variables named in `names_for_user`. Each name's value comes from the first of these that
defines it:

1. A variable that `setup_code.py` defines.
2. `starting_vars` in the [`ConfigObject`](#configuration-with-configobject).
3. `data["params"]` from `data.json`.

`names_for_user` comes from the `ConfigObject` if it's set there, as a list of strings. Otherwise
it comes from `data["params"]["names_for_user"]`, a list of `{"name": ..., "description": ...,
"type": ...}` objects, which `<pl-external-grader-variables params-name="names_for_user">` in
`question.html` usually sets. Without `names_for_user`, student code gets no variables, and using
one fails with a `NameError`. `names_from_user` only displays a table in the question, and the
grader ignores it.

### Parameters from `server.py`

When `server.py` randomizes plain values, list them in `names_for_user` and read them in tests with
the `data_json` fixture:

```python
# server.py
import random


def generate(data):
    data["params"]["n"] = random.randint(5, 10)
```

```html
<!-- question.html -->
<pl-external-grader-variables params-name="names_for_user">
  <pl-variable name="n" type="integer">The number of terms</pl-variable>
</pl-external-grader-variables>
```

```python
# tests/test_student.py
@pytest.mark.grading_data(name="total", points=1)
def test_total(sandbox: StudentFixture, data_json: dict) -> None:
    n = data_json["params"]["n"]
    assert_equal(sandbox.query("total"), n * (n + 1) // 2, description="total")
```

### Fixed Values

For a value that's the same in every variant, use `starting_vars`:

```python
autograder_config = ConfigObject(starting_vars={"threshold": 5.0}, names_for_user=["threshold"])
```

### Setup Code (`setup_code.py`)

Use setup code when a value needs Python to build, such as a numpy array. It runs in the sandbox
before the student's code:

```python
import numpy as np
import numpy.linalg as la

n = np.random.randint(4, 16)

# A random full-rank matrix
X = la.qr(np.random.random_sample((n, n)))[0]
D = np.diag(np.random.random_sample(n) * 10 + 1)
A = X.T @ D @ X
b = np.random.random(n)
```

With `names_for_user` set to `A`, `b` and `n`, student code gets those three variables. To stop
students from calling a library function such as `la.inv`, use
[`import_blacklist`](#blocking-functions) rather than setup code.

- **Parameters.** `__data_params` holds `data["params"]`. Values that `server.py` stored with
  `pl.to_json` are still encoded: decode them with `__from_server_json`, for example
  `A = __from_server_json(__data_params["A"])`. The `prairielearn` package isn't available.
- **Restrictions.** Setup code has the same builtins and import rules as student code. For example,
  it can't call `open` or import `os`. To read a data file, list it in [`data_files`](#data-files).
- **Fresh values.** With the `sandbox` fixture, setup code runs again for each test, so random
  values differ between tests. Read a setup value in the test that uses it, with
  [`sandbox.query_setup`](#5-query-setup-variables).

## Configuration

### Configuration with ConfigObject

For complex test scenarios, you can use the `ConfigObject` class to configure all autograder settings
in a single, type-safe, immutable object. This is especially useful when you need to override multiple
settings or want better IDE support with autocomplete and type checking.

**Key Features:**

- **Type-safe**: All parameters are type-checked with validation
- **Immutable**: Configuration cannot be modified after creation (frozen dataclass)
- **Keyword-only**: Must use explicit parameter names for clarity
- **Comprehensive**: Supports all security and execution settings

#### Basic Usage

Import and create a `ConfigObject` at the module level in your `test_student.py`:

```python
from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.assertions import assert_equal, assert_true
from pytest_prairielearn_grader.fixture import StudentFixture
import pytest

# Module-level configuration - detected automatically by the plugin
autograder_config = ConfigObject(
    sandbox_timeout=2.0,
    import_whitelist=["numpy", "pandas"],
    builtin_whitelist=["getattr", "hasattr"],
    starting_vars={"coefficient": 10, "threshold": 5.0},
    names_for_user=["coefficient", "threshold"],
)

@pytest.mark.grading_data(name="Test with Config", points=5)
def test_with_config(sandbox: StudentFixture) -> None:
    # Configuration is automatically applied
    result = sandbox.query_function("process", data)
    assert_equal(result, expected_value)
```

#### ConfigObject Parameters

All parameters are optional:

| Parameter                  | Default                                            | Description                                                                                                                                |
| -------------------------- | -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `sandbox_timeout`          | `1.0`                                              | Seconds allowed for starting the sandbox, which runs the setup code and student code. See [Timeout Configuration](#timeout-configuration). |
| `output_level`             | `None`                                             | Default [output level](#output-levels) for every test.                                                                                     |
| `names_for_user`           | `None`                                             | Variables to give student code. See [Giving Values to Student Code](#giving-values-to-student-code).                                       |
| `starting_vars`            | `{}`                                               | Values for names in `names_for_user`.                                                                                                      |
| `student_code_pattern`     | `"student_code*.py"`                               | Glob pattern for the student's file.                                                                                                       |
| `import_whitelist`         | `None`                                             | Modules that code in the sandbox may import. `None` allows all. See [Import Control](#import-control).                                     |
| `import_blacklist`         | `["os", "sys", "subprocess", "pathlib", "shutil"]` | Modules and functions that code in the sandbox may not use. See [Blocking Functions](#blocking-functions).                                 |
| `builtin_whitelist`        | `None`                                             | Builtins to allow beyond the safe defaults. See [Builtin Function Control](#builtin-function-control).                                     |
| `helper_modules`           | `None`                                             | Modules from the tests folder that can be imported. See [Helper Modules](#helper-modules).                                                 |
| `data_files`               | `None`                                             | Files from the tests folder that code in the sandbox can read by relative path. See [Data Files](#data-files).                             |
| `syntax_errors_ungradable` | `True`                                             | Whether a syntax error makes the submission ungradable. See [Ungradable Submission Detection](#ungradable-submission-detection).           |
| `notebook_cell_tag`        | `None`                                             | Grade only notebook cells that start with this tag. See [Jupyter Notebook Grading](#jupyter-notebook-grading).                             |
| `workspace_mode`           | `False`                                            | Grade a multi-file project. See [Workspace Grading](#workspace-grading).                                                                   |
| `workspace_student_dir`    | `None`                                             | The student's project folder in workspace mode.                                                                                            |
| `workspace_exec_entry`     | `None`                                             | A file to run at startup in workspace mode.                                                                                                |

#### Helper Modules

The tests folder isn't on the import path in the sandbox, and `import_whitelist` only permits a
name. To let setup code and student code import a file from that folder, name it
in `helper_modules`:

```python
# tests/test_student.py, with the helper in tests/helper_function.py
autograder_config = ConfigObject(helper_modules=["helper_function"])
```

```python
# the student's code, or setup code
import helper_function as hf
```

- **Names:** each entry is a plain module name, without dots, paths or `.py`. Packages aren't supported.
- **Everything else stays out:** other files in the folder, such as `test_student.py`, still can't be
  imported, even if they're in `import_whitelist`.
- **Import restrictions:** a listed module doesn't need to be in `import_whitelist`. Listing one that
  `import_blacklist` also blocks is a configuration error.
- **Inside a helper module:** it runs with the same builtins and import rules as student code. For
  example, it can't use `getattr` or import `numpy` unless those are allowed.
- **Configuration errors:** if a listed file is missing or has a syntax error, or the module is
  blacklisted, the submission is ungradable. The students don't lose an attempt, and each test's
  message says what's wrong.
- **Fixtures:** it works with `sandbox` and `module_sandbox`, for `.py` and `.ipynb` submissions, and
  with `workspace_sandbox`.
- **Workspace mode:** students can have several files that import each other, so a listed name is
  reserved. If a student submits a `helper_function.py` or a `helper_function/` folder, the
  submission fails with a message asking them to rename it and counts as an attempt. Don't give
  students a copy of a helper module in their workspace. A listed module keeps the restricted builtins
  that the student's own modules don't have. Dotted queries such as
  `query_function("helper_function.triple")` only search the student's project, so they won't call a
  helper module.

> **Warning:** Students can read everything in a helper module, so it must not contain answers. This
> setting also doesn't make the rest of the tests folder private. `importlib` isn't blacklisted by
> default, so student code can load files in that folder by path.

#### Data Files

In a workspace, code such as `np.loadtxt("pagerank_large.txt")` reads a file next to the notebook. To
make the same code work during grading, put the file in the tests folder and name it in `data_files`:

```python
# tests/test_student.py, with the data in tests/pagerank_large.txt
autograder_config = ConfigObject(
    data_files=["pagerank_large.txt"],
    student_code_pattern="Markov-Chains-3.ipynb",
    notebook_cell_tag="#grade",
)


def test_pagerank(sandbox: StudentFixture, tests_dir: Path) -> None:
    edges = np.loadtxt(tests_dir / "pagerank_large.txt")  # the instructor's original
    ...
```

```python
# the student's code, or setup code
edges = np.loadtxt("pagerank_large.txt")
```

- **Paths:** each entry is relative to the tests folder, such as `"pagerank_large.txt"` or
  `"data/points.csv"`, and keeps that relative path in the sandbox. Absolute paths and `..` aren't
  accepted.
- **Starting folder:** the sandbox starts in a new folder that holds only copies of the listed files.
  Without `data_files`, the starting folder isn't changed.
- **Read-only copies:** the copies and their folder are read-only for student code, and a fresh copy is
  made for each sandbox. Tests should read the originals through the `tests_dir` fixture.
- **Reading, not importing:** the folder isn't on the import path, so a listed `.py` file can't be
  imported. Use `helper_modules` for that.
- **Configuration errors:** if a listed file is missing, the submission is ungradable. The students
  don't lose an attempt, and each test's message says what's wrong.
- **Fixtures:** it works with `sandbox` and `module_sandbox`, for `.py` and `.ipynb` submissions, and
  with `workspace_sandbox`. In workspace mode, relative paths resolve against the data files' folder,
  not the student's workspace folder.

> **Warning:** Students can read the listed files, so they must not contain answers.

#### Configuration Priority

When `ConfigObject` is defined, it overrides all other configuration sources:

1. **Highest priority**: `ConfigObject` (when `autograder_config` variable exists)
2. **Medium priority**: Module-level variables (e.g., `sandbox_timeout = 2.0`)
3. **Lowest priority**: `data.json` params from PrairieLearn

```python
# This ConfigObject overrides everything
autograder_config = ConfigObject(
    sandbox_timeout=3.0,  # Overrides module-level timeout
    import_whitelist=["numpy"],  # Overrides data.json import_whitelist
    starting_vars={"x": 10},  # Overrides data.json params["x"]
    names_for_user=["x"],
)

# This module-level timeout is ignored when ConfigObject is present
sandbox_timeout = 1.0
```

#### Complete Example

```python
from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.assertions import assert_equal, assert_true
from pytest_prairielearn_grader.fixture import StudentFixture, FeedbackFixture
import pytest

# Comprehensive configuration
autograder_config = ConfigObject(
    # Execution settings
    sandbox_timeout=2.5,

    # Security: only allow scientific computing libraries
    import_whitelist=["numpy", "scipy", "matplotlib"],

    # Allow builtins that the defaults leave out
    builtin_whitelist=["getattr", "hasattr"],

    # Provide test data
    starting_vars={
        "input_data": [1, 2, 3, 4, 5],
        "multiplier": 2.5,
        "threshold": 10,
    },

    # Explicitly list what gets injected
    names_for_user=["input_data", "multiplier", "threshold"],
)

@pytest.mark.grading_data(name="Test Processing", points=10)
def test_data_processing(sandbox: StudentFixture, feedback: FeedbackFixture) -> None:
    # All configuration from ConfigObject is automatically applied
    result = sandbox.query_function("process_data")

    assert_true(len(result) > 0, msg="Result should not be empty")
    feedback.set_score(0.5)

    assert_true(result == expected_output, msg="Incorrect processing result")
    feedback.set_score(1.0)
```

#### Validation

`ConfigObject` validates all parameters at creation time:

```python
# ✓ Valid configuration
config = ConfigObject(
    sandbox_timeout=2.0,
    import_whitelist=["numpy"],
)

# ✓ Valid: can combine whitelist and blacklist
config = ConfigObject(
    import_whitelist=["numpy", "matplotlib"],
    import_blacklist=["matplotlib.pyplot"]  # Block pyplot specifically
)

# ✗ Error: timeout must be positive
config = ConfigObject(sandbox_timeout=-1.0)  # ValueError

# ✗ Error: must use keyword arguments
config = ConfigObject(2.0)  # TypeError

# ✗ Error: names_for_user must contain strings
config = ConfigObject(names_for_user=[123, 456])  # ValueError
```

### Timeout Configuration

Control execution time limits for sandbox initialization and function calls to prevent infinite loops or slow student code.

**Important**: Timeouts apply to:

- **Sandbox initialization** (loading and executing student code at startup)
- **Function calls** via `sandbox.query_function()` with `query_timeout` parameter

Variable queries via `sandbox.query()` do not have timeouts since they're simple lookups.

#### Module-level Default Timeout

Set a default timeout for sandbox initialization in all tests in a file. This variable and the
`sandbox_timeout` marker below are ignored when the file has an `autograder_config`, so use
`ConfigObject(sandbox_timeout=...)` there instead.

```python
import pytest
from pytest_prairielearn_grader.assertions import assert_equal, assert_true
from pytest_prairielearn_grader.fixture import StudentFixture

sandbox_timeout = 2.0  # 2 second timeout for initialization


@pytest.mark.grading_data(name="Test 1", points=1)
def test_with_default_timeout(sandbox: StudentFixture) -> None:
    # The sandbox was initialized with 2 second timeout
    # Now we can safely query variables and call functions
    result = sandbox.query_function("compute_result")
    assert_equal(result, 5)
```

#### Per-test Timeout Override

Override the default initialization timeout with the `@pytest.mark.sandbox_timeout` marker:

```python
@pytest.mark.grading_data(name="Fast Test", points=1)
@pytest.mark.sandbox_timeout(0.5)  # 0.5 second initialization timeout
def test_with_custom_timeout(sandbox: StudentFixture) -> None:
    # This sandbox was initialized with 0.5 second timeout
    result = sandbox.query_function("quick_computation")
    assert_equal(result, 5)
```

#### Per-function Timeout

Set timeout for individual function calls using the `query_timeout` parameter:

```python
@pytest.mark.grading_data(name="Function Test", points=2)
def test_function_timeout(sandbox: StudentFixture) -> None:
    # This specific function call has a 1 second timeout
    result = sandbox.query_function("compute", data, query_timeout=1.0)
    assert_equal(result, expected_value)

    # This function call uses the default timeout (no per-function limit)
    result2 = sandbox.query_function("another_compute", data)
    assert_equal(result2, expected_value2)
```

**Using ConfigObject for timeouts:**

```python
from pytest_prairielearn_grader import ConfigObject

autograder_config = ConfigObject(
    sandbox_timeout=3.0,  # Sets initialization timeout
)

@pytest.mark.grading_data(name="Test", points=1)
def test_with_config_timeout(sandbox: StudentFixture) -> None:
    # Initialized with 3 second timeout from ConfigObject
    result = sandbox.query_function("process", query_timeout=1.0)
    assert_equal(result, expected)
```

### Security: Import and Builtin Restrictions

Control which Python modules and builtin functions students can use in their code. This is crucial for:

- **Security**: Preventing access to file system, network, or system operations
- **Pedagogical constraints**: Requiring students to implement functionality from scratch
- **Resource management**: Blocking operations that consume excessive resources

#### Import Control

Restrict which Python modules students can import using whitelists or blacklists.

**Import Whitelist**: Only allow specific modules:

```python
# In server.py (PrairieLearn question)
def generate(data):
    data["params"]["import_whitelist"] = ["numpy", "math", "statistics"]
    # Only numpy, math, and statistics can be imported
    # Attempting to import any other module raises ImportError
```

**Import Blacklist**: Block specific modules while allowing all others:

```python
# In server.py
def generate(data):
    data["params"]["import_blacklist"] = ["os", "subprocess", "sys"]
    # os, subprocess, and sys cannot be imported
    # All other modules are allowed
```

**Combining Whitelist and Blacklist**: Use both for fine-grained control (blacklist checked first):

```python
# In server.py
def generate(data):
    # Allow scientific libraries but block specific dangerous submodules
    data["params"]["import_whitelist"] = ["numpy", "scipy", "matplotlib"]
    data["params"]["import_blacklist"] = ["matplotlib.pyplot"]  # Block pyplot even though matplotlib is allowed
    # Result: numpy, scipy, and matplotlib are allowed, but matplotlib.pyplot is blocked
```

**Example student code with import whitelist:**

```python
# data.json has "import_whitelist": ["numpy", "math"]

import numpy as np  # ✓ Allowed
import math  # ✓ Allowed
from numpy import array  # ✓ Allowed

import os  # ✗ ImportError: Module 'os' is not allowed to be imported
import pandas  # ✗ ImportError: Module 'pandas' is not allowed to be imported
```

**Example with import inside function:**

```python
def my_function():
    import os  # ✗ This will raise ImportError when the function is called
    return os.getcwd()
```

**Note**: Blacklist is checked first, then whitelist. If a whitelist is specified, only those modules (minus any in blacklist) can be imported. If only a blacklist is specified, those modules are blocked but all others are allowed.

A blacklisted module also blocks its submodules, however they're imported. With `"os"` in the blacklist, `import os.path` is blocked as well as `import os`. With `"matplotlib.pyplot"`, both `import matplotlib.pyplot` and `from matplotlib import pyplot` are blocked, but `import matplotlib` still works.

The blacklist only checks import statements, so it isn't a security boundary. For example, modules that student code is allowed to import can expose `os` as an attribute.

#### Blocking Functions

To stop students from using one library function, such as `numpy.linalg.inv` in a question about
solving linear systems, add the function to `import_blacklist`:

```python
autograder_config = ConfigObject(
    import_blacklist=["os", "sys", "subprocess", "pathlib", "shutil", "numpy.linalg.inv", "numpy.linalg.pinv"],
    sandbox_timeout=15,
)
```

Setting `import_blacklist` replaces the default list, so keep its entries.

Before setup code runs, the sandbox replaces each listed function in its module with one that
raises an error. So `np.linalg.inv(A)` and `la.inv(A)` raise
`RuntimeError: 'numpy.linalg.inv' is blacklisted and cannot be used.`, and
`from numpy.linalg import inv` raises an `ImportError`. This is the preferred way to block a
function: don't override it in setup code.

- **Which entries:** an entry is treated as a function when the part before its last dot is a module
  that can be imported and the last part is a callable that isn't a module. Other entries, such as
  `"os"` or `"matplotlib.pyplot"`, block imports as described above. If the module isn't installed
  in the image, the entry does nothing.
- **Setup code and helper modules** can't call the function either, because they share the
  sandbox's modules. Compute values that need it in the test instead.
- **Startup time:** the function's module is imported when the sandbox starts, even if the student's
  code doesn't use it.
- **Not a security boundary:** the function can still be reached under another name, such as
  numpy's internal `numpy.linalg._linalg.inv`.

#### Builtin Function Control

Setup code, student code and helper modules get only these builtins by default:

- Types: `bool`, `bytearray`, `bytes`, `complex`, `dict`, `float`, `frozenset`, `int`, `list`,
  `object`, `set`, `slice`, `str`, `tuple`, `type`
- Type checking: `callable`, `isinstance`, `issubclass`
- Iteration: `all`, `any`, `enumerate`, `filter`, `iter`, `map`, `next`, `range`, `reversed`,
  `sorted`, `zip`
- Math: `abs`, `divmod`, `max`, `min`, `pow`, `round`, `sum`
- Conversion: `ascii`, `bin`, `chr`, `format`, `hash`, `hex`, `id`, `oct`, `ord`, `repr`
- Classes: class definitions, `classmethod`, `property`, `staticmethod`, `super`
- Other: `len`, `print`, `None`, `True`, `False`, `Ellipsis`, `NotImplemented`
- The standard exception classes, such as `ValueError`

Builtins that read or change attributes and namespaces by name, such as `getattr`, `hasattr`,
`setattr`, `vars`, `dir` and `globals`, aren't in this list. Student code that uses one fails with a
`NameError`, so add the ones your question's solutions need to `builtin_whitelist`. A builtin in
the default list can't be removed with `builtin_whitelist`.

**Dangerous builtins automatically blocked** include: `open`, `eval`, `exec`, `compile`, `__import__`, `input`, `exit`, `quit`, and others that could compromise security.

**Builtin Whitelist**: Grant access to additional builtin functions:

```python
# In server.py
def generate(data):
    data["params"]["builtin_whitelist"] = ["getattr", "hasattr"]
    # Students can now use getattr() and hasattr() in addition to the defaults
```

**Example with builtin whitelist:**

```python
# data.json has "builtin_whitelist": ["getattr"]

# Default builtins work normally:
my_list = [1, 2, 3]  # ✓ list is a default
length = len(my_list)  # ✓ len is a default
print(length)  # ✓ print is a default

# Whitelisted builtins work:
count = getattr(my_list, "count")(1)  # ✓ getattr is in the whitelist

# Other builtins are blocked:
names = dir(my_list)  # ✗ NameError: name 'dir' is not defined

# Dangerous builtins are blocked:
f = open("file.txt")  # ✗ NameError: 'open' is not defined
result = eval("1+1")  # ✗ NameError: 'eval' is not defined
```

#### Combining Security Features

You can combine import and builtin restrictions for comprehensive control:

```python
# In server.py
def generate(data):
    # Allow only numpy and math imports
    data["params"]["import_whitelist"] = ["numpy", "math"]

    # Allow getattr for student convenience
    data["params"]["builtin_whitelist"] = ["getattr"]

    # Now students can:
    # - Import numpy and math
    # - Use getattr() plus the default builtins
    # - Cannot import other modules
    # - Cannot use dangerous builtins like open(), eval()
```

#### PrairieLearn Server.py Configuration

In your PrairieLearn question's `server.py`, add these parameters during the `generate()` step:

```python
import prairielearn as pl

def generate(data):
    # Set up question parameters
    data["params"]["n"] = 5
    data["params"]["A"] = pl.to_json(np.random.rand(5, 5))

    # Configure security restrictions
    data["params"]["import_whitelist"] = ["numpy", "numpy.linalg"]
    data["params"]["builtin_whitelist"] = ["getattr"]

    # Define variables accessible to student code
    data["params"]["names_for_user"] = [
        {"name": "n", "description": "Matrix dimension", "type": "integer"},
        {"name": "A", "description": "Input matrix", "type": "numpy array"}
    ]
```

These parameters are automatically passed to the autograder via `/grade/data/data.json` and enforced during student code execution.

In the grader images, `run.sh` passes this path to pytest with `--data-json-path` and makes the file readable only by root, so student code can't open it. The file can contain `correct_answers`. Without that option, for example when running locally, the fixture reads `data.json` next to your test file. The sandbox still receives `params` through `__data_params`, so don't rely on values in `params` staying hidden from student code.

#### Testing Import/Builtin Restrictions Locally

To test your restrictions in the test scenarios:

```python
# tests/test_student.py
import pytest
from pytest_prairielearn_grader.assertions import assert_equal, assert_true
from pytest_prairielearn_grader.fixture import StudentFixture

@pytest.mark.grading_data(name="Test with restrictions", points=5)
def test_security(sandbox: StudentFixture) -> None:
    """Test that imports are properly restricted."""
    # If student code tries to import blocked modules,
    # the sandbox will raise an ImportError during initialization
    result = sandbox.query_function("safe_function", data)
    assert_equal(result, expected)
```

```python
# data.json
{
  "params": {
    "import_whitelist": ["numpy", "math"],
    "builtin_whitelist": ["getattr"],
    "names_for_user": [...]
  }
}
```

#### Common Use Cases

**1. Force students to implement algorithms from scratch:**

```python
# Require students to implement algorithms without libraries
data["params"]["import_whitelist"] = []  # No imports allowed
# Default builtins such as sorted() and sum() are still available.
```

**2. Allow numerical computing but block system access:**

```python
# Scientific computing course
data["params"]["import_whitelist"] = ["numpy", "scipy", "matplotlib", "pandas"]
# Safe builtins are automatically enforced (no open, eval, etc.)
```

**3. Block dangerous operations explicitly:**

```python
# Block system and file operations
data["params"]["import_blacklist"] = ["os", "sys", "subprocess", "pathlib", "shutil"]
# All other imports allowed, but dangerous ones explicitly blocked
```

## Ungradable Submission Detection

When student code has a **SyntaxError** (e.g., missing colons, unmatched brackets, bad indentation),
the grader automatically marks the submission as **ungradable**. This means:

- The student does **not** lose a grading attempt
- They see a clear message: _"Your code could not be parsed. Please fix the syntax errors and resubmit."_
- The `format_errors` field in results contains the specific error

This is especially useful for introductory courses where students may accidentally submit code
with trivial syntax mistakes.

### How It Works

The grader detects `SyntaxError` during sandbox initialization (when `compile()` is called on
student code). Instead of failing all tests with 0%, it produces:

```json
{
  "gradable": false,
  "format_errors": ["SyntaxError: invalid syntax (student_code.py, line 3)"],
  "message": "Your code could not be parsed. Please fix the syntax errors and resubmit.",
  "tests": [...]
}
```

PrairieLearn's external grading framework handles the `"gradable": false` field — the student's
submission is marked as "invalid, not gradable", no points are awarded or lost, and the student
is not penalized an attempt. See the
[PrairieLearn external grading docs](https://docs.prairielearn.com/externalGrading/#grading-results)
for full details on the `results.json` format.

### Disabling Ungradable Detection

If you prefer syntax errors to score 0% (counting as a normal attempt), opt out in your config:

```python
from pytest_prairielearn_grader import ConfigObject

autograder_config = ConfigObject(
    syntax_errors_ungradable=False,  # SyntaxError → 0% instead of ungradable
)
```

### Grader-Side Errors

The grader also detects when **test files themselves** fail to collect (e.g., import errors in
your test code, missing dependencies). These are marked as ungradable with a message directing
course staff to check the logs — students are never penalized for grader bugs.

## Jupyter Notebook Grading

PrairieLearn supports JupyterLab as a workspace environment
(`prairielearn/workspace-jupyterlab-python`), and students commonly submit `.ipynb` files from
other IDE-based workspaces too. The autograder handles notebooks natively: it extracts the Python
source from the relevant code cells, concatenates them into a single script, and executes that
script in the sandbox exactly like a normal `.py` submission. Every fixture, query method, and
partial credit feature works identically — no special test-writing API is needed.

> **Optional dependency**: Notebook support requires `nbformat`.
> Install it with `pip install 'pytest-prairielearn-grader[notebook]'`.
> The core package deliberately does **not** depend on `nbformat` so that grader images without
> Jupyter installed remain lightweight.

### Telling the Grader to Look for Notebooks

The only required change is updating `student_code_pattern` in your `ConfigObject` to match
`.ipynb` files:

```python
from pytest_prairielearn_grader import ConfigObject

autograder_config = ConfigObject(
    student_code_pattern="student_code*.ipynb",
    sandbox_timeout=5.0,
)
```

All code cells are extracted in notebook order and concatenated, so functions and variables
defined in earlier cells are available in later ones — exactly as they are when the notebook is
executed top-to-bottom in JupyterLab.

### Filtering Cells with `notebook_cell_tag`

Real student notebooks often contain scratch work, exploratory plots, and print statements that
you don't want to run during grading. Use `notebook_cell_tag` to restrict extraction to only the
cells the student intended to submit:

```python
autograder_config = ConfigObject(
    student_code_pattern="student_code*.ipynb",
    notebook_cell_tag="#grade",   # only cells whose first line starts with "#grade"
    sandbox_timeout=5.0,
)
```

A code cell is included if and only if its **first non-empty line starts with the tag string**.
All other cells — including cells that would raise errors or produce unwanted side effects — are
silently skipped.

**Student notebook example:**

```python
# Cell 1 — scratch work (NOT included, no tag)
import matplotlib.pyplot as plt
plt.plot([1, 2, 3])
plt.show()

# Cell 2 — graded solution (included, starts with #grade)
#grade
def solve(A, b):
    import numpy as np
    return np.linalg.solve(A, b)

# Cell 3 — another graded cell (included, starts with #grade)
#grade
x = solve([[1, 0], [0, 2]], [3, 8])
```

Only cells 2 and 3 are extracted and run. Cell 1 is completely ignored, so the `plt.show()` call
never reaches the sandbox.

> `notebook_cell_tag=None` (the default) includes **all** code cells. Use this when you control
> the notebook template and don't need students to tag their answers.

### `info.json` for a JupyterLab Notebook Question

```json
{
  "uuid": "...",
  "title": "Linear Algebra — Notebook Submission",
  "topic": "...",
  "tags": ["..."],
  "type": "v3",
  "singleVariant": true,
  "gradingMethod": "External",
  "workspaceOptions": {
    "image": "prairielearn/workspace-jupyterlab-python",
    "port": 8080,
    "home": "/home/user",
    "gradedFiles": ["notebook.ipynb"]
  },
  "externalGradingOptions": {
    "enabled": true,
    "image": "prairielearn/grader-python-pytest:latest",
    "timeout": 60
  }
}
```

> Set `singleVariant: true` so the workspace — and any work saved in it — persists across
> multiple submission attempts.

### Writing Tests for Notebook Submissions

Tests are written the same way as for any other submission type. There is nothing
notebook-specific in the test file beyond `student_code_pattern` (and optionally
`notebook_cell_tag`) in the `ConfigObject`:

```python
import pytest
import numpy as np

from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.assertions import assert_equal, assert_true
from pytest_prairielearn_grader.fixture import FeedbackFixture, StudentFixture

autograder_config = ConfigObject(
    student_code_pattern="notebook*.ipynb",
    notebook_cell_tag="#grade",
    sandbox_timeout=10.0,
)


@pytest.mark.grading_data(name="solve() is correct", points=5)
def test_solve(sandbox: StudentFixture, feedback: FeedbackFixture) -> None:
    A = [[2, 1], [1, 3]]
    b = [5, 10]
    feedback.set_score(0.0)

    result = sandbox.query_function("solve", A, b)
    feedback.set_score(0.5)

    expected = np.linalg.solve(A, b)
    assert_true(np.allclose(result, expected), msg="solve(A, b) is inaccurate")
    feedback.set_score(1.0)


@pytest.mark.grading_data(name="result variable is set", points=2)
def test_result_variable(sandbox: StudentFixture, feedback: FeedbackFixture) -> None:
    feedback.set_score(0.0)
    x = sandbox.query("x")
    assert_true(x is not None, msg="Variable 'x' was not defined")
    feedback.set_score(1.0)
```

### ConfigObject Settings for Notebooks

| Parameter              | Type          | Default              | Description                                                                                       |
| ---------------------- | ------------- | -------------------- | ------------------------------------------------------------------------------------------------- |
| `student_code_pattern` | `str`         | `"student_code*.py"` | Glob pattern — change to `"*.ipynb"` or `"notebook*.ipynb"` to match notebook files.              |
| `notebook_cell_tag`    | `str \| None` | `None`               | First-line tag for cell filtering. `None` = all cells. Cannot be used with `workspace_mode=True`. |
| `sandbox_timeout`      | `float`       | `1.0`                | Increase to 5–15 s for notebooks with heavy imports or large cell computations.                   |

### Production vs. Local Development

In production PrairieLearn, the submitted `gradedFiles` end up in `/grade/student/`. The grader
searches for matching files there automatically. For local development, place the notebook in the
tests folder next to your test file (the folder named after it):

```
questions/my_notebook_question/
└── tests/
    ├── test_student.py
    └── test_student/
        └── notebook.ipynb     # local stand-in for the student's submission
```

## Workspace Grading

PrairieLearn workspace questions give students a full IDE (VS Code, JupyterLab, etc.) running in a
browser. When a student clicks **Submit**, PrairieLearn copies the files listed in `gradedFiles`
out of their workspace container and into `/grade/student/`, preserving all directory structure.

The `workspace_sandbox` fixture is designed specifically for this use case. Unlike the regular
`sandbox` fixture (which `exec`s a single file), the workspace fixture adds the student's project
directory to `sys.path` and lets tests interact with the project using Python's normal import
machinery — exactly the same way you would test a local Python package.

### Why a separate fixture?

|              | `sandbox`                          | `workspace_sandbox`                      |
| ------------ | ---------------------------------- | ---------------------------------------- |
| Student code | Single file                        | Multi-file project                       |
| Startup      | `exec` the file                    | Set `sys.path`, import on demand         |
| Querying     | Flat variable/function names       | Dotted module paths (`"models.predict"`) |
| Use case     | `pl-file-editor`, `pl-file-upload` | Workspace questions                      |

### File Structure

For a PrairieLearn workspace question the grader sees this layout at runtime:

```
/grade/
├── data/
│   └── data.json          # question parameters
├── student/               # gradedFiles copied from student's workspace
│   ├── calculator.py
│   ├── utils/
│   │   ├── __init__.py
│   │   └── helpers.py
│   └── main.py
└── tests/                 # copies of your question's tests/ directory
    ├── setup_code.py      # (optional)
    └── test_student.py
```

For **local development**, mirror this by creating a `student/` sub-directory next to your test
file. The fixture finds it automatically without any configuration:

```
questions/my_workspace_question/
├── info.json
├── question.html
└── tests/
    ├── test_student.py        # your test file
    ├── setup_code.py          # (optional)
    └── test_student/          # ← mirrors the tests folder layout
        └── student/           # ← local stand-in for /grade/student
            ├── calculator.py
            └── utils/
                ├── __init__.py
                └── helpers.py
```

### `info.json` Configuration

```json
{
  "uuid": "...",
  "title": "Calculator Project",
  "topic": "...",
  "tags": ["..."],
  "type": "v3",
  "singleVariant": true,
  "gradingMethod": "External",
  "workspaceOptions": {
    "image": "prairielearn/workspace-vscode-python",
    "port": 8080,
    "home": "/home/user",
    "gradedFiles": ["calculator.py", "utils/*.py", "utils/__init__.py"]
  },
  "externalGradingOptions": {
    "enabled": true,
    "image": "prairielearn/grader-python-pytest:latest",
    "timeout": 30
  }
}
```

**Key points:**

- `gradedFiles` controls which files are copied from the workspace into `/grade/student/`.
  Use glob patterns (`utils/*.py`) to capture whole directories.
- `singleVariant: true` prevents the workspace from resetting between attempts.

### Writing Tests

Use `workspace_sandbox` and query student code with **dotted module paths**:

```python
from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.assertions import assert_equal, assert_true
from pytest_prairielearn_grader.fixture import WorkspaceFixture
import pytest

autograder_config = ConfigObject(
    workspace_mode=True,
    sandbox_timeout=10.0,
)

@pytest.mark.grading_data(name="Add two numbers", points=2)
def test_add(workspace_sandbox: WorkspaceFixture) -> None:
    result = workspace_sandbox.query_function("calculator.add", 3, 4)
    assert_equal(result, 7)


@pytest.mark.grading_data(name="Clamp from sub-package", points=2)
def test_clamp(workspace_sandbox: WorkspaceFixture) -> None:
    result = workspace_sandbox.query_function("utils.helpers.clamp", 15, 0, 10)
    assert_equal(result, 10)


@pytest.mark.grading_data(name="Module-level constant", points=1)
def test_constant(workspace_sandbox: WorkspaceFixture) -> None:
    pi = workspace_sandbox.query("calculator.PI_APPROX")
    assert_true(abs(pi - 3.14159) < 1e-5)
```

The dotted path is split on the **last dot**: `"calculator.add"` imports the module `calculator`
and calls `getattr(calculator, "add")`. This means:

| Query string                | Module imported   | Attribute retrieved |
| --------------------------- | ----------------- | ------------------- |
| `"calculator.add"`          | `calculator`      | `add`               |
| `"utils.helpers.clamp"`     | `utils.helpers`   | `clamp`             |
| `"models.nn.Model.predict"` | `models.nn.Model` | `predict`           |

### Querying Variables vs. Functions

Both `query` and `query_function` understand dotted paths:

```python
# Query a module-level variable
eps = workspace_sandbox.query("utils.helpers.EPSILON")

# Query a class defined in a module
result = workspace_sandbox.query_function("models.Classifier.predict", X_test)

# query_function_raw — inspects the full response without raising
response = workspace_sandbox.query_function_raw("calculator.divide", 1, 0)
assert_equal(response["status"], "exception")
assert_equal(response["exception_name"], "ValueError")
```

### Optional: Entry-Point Execution

Some workspace questions have a `main.py` that sets up global state before tests run. Use
`workspace_exec_entry` to `exec` it at sandbox startup:

```python
autograder_config = ConfigObject(
    workspace_mode=True,
    workspace_exec_entry="main.py",  # exec'd from workspace root at startup
    sandbox_timeout=15.0,
)

# Now the sandbox namespace includes everything main.py defined at module level
def test_global_state(workspace_sandbox: WorkspaceFixture) -> None:
    db = workspace_sandbox.query("database")  # flat name - set by main.py via exec
    assert_true(db is not None)
```

Without `workspace_exec_entry` (the default), no file is executed at startup and all access
goes through the import machinery.

### Student Files Named Like Loaded Modules

The sandbox loads some modules for itself before any student or setup code runs, such as
`random`, `json`, `types`, `typing`, `logging` and `math`. Python reuses a module that's already
loaded, so a student file named `random.py` (or a folder named `json/`) at the top of the project
would be silently ignored in favor of the standard library module.

Instead, startup fails and every test is an error worth 0 points, with a message listing the files
and asking the student to rename them:

```text
Student code execution failed with an exception: ImportError
Exception Message: These names are already used by modules that the grader has loaded: json/, random.py. Rename yours and update any imports that use them.
```

Only top-level `.py` files and folders are checked, and only against modules the sandbox has
actually loaded. A file such as `calendar.py` or `utils.py` that doesn't match a loaded module is
imported normally. The list of loaded modules can change between Python versions.

### ConfigObject Settings for Workspaces

| Parameter               | Type                | Default      | Description                                                                                                   |
| ----------------------- | ------------------- | ------------ | ------------------------------------------------------------------------------------------------------------- |
| `workspace_mode`        | `bool`              | `False`      | Enable workspace grading mode                                                                                 |
| `workspace_student_dir` | `str \| None`       | `None`       | Path to student project root. Defaults to `student/` next to tests. Set to `"/grade/student"` for production. |
| `workspace_exec_entry`  | `str \| None`       | `None`       | Relative path (from workspace root) to an entry-point file to `exec` at startup.                              |
| `sandbox_timeout`       | `float`             | `1.0`        | Timeout for sandbox startup (increase for larger projects).                                                   |
| `import_whitelist`      | `list[str] \| None` | `None`       | Allowed imports. `None` = allow all.                                                                          |
| `import_blacklist`      | `list[str] \| None` | default list | Blocked imports and functions.                                                                                |
| `helper_modules`        | `list[str] \| None` | `None`       | Modules from the tests folder to make importable. See [Helper Modules](#helper-modules).                      |

### Production vs. Local Development

The `workspace_student_dir` path differs between environments:

```python
# Production (running on PrairieLearn): set an absolute path
autograder_config = ConfigObject(
    workspace_mode=True,
    workspace_student_dir="/grade/student",
)

# Local dev: omit the field — the fixture finds student/ automatically
autograder_config = ConfigObject(
    workspace_mode=True,
    # workspace_student_dir defaults to student/ next to your test file
)
```

A common pattern is to use an environment variable so one config works in both environments:

```python
import os

autograder_config = ConfigObject(
    workspace_mode=True,
    workspace_student_dir=os.environ.get("STUDENT_DIR"),  # None → auto-detect locally
    sandbox_timeout=10.0,
)
```

### Security Notes

- The default `import_blacklist` (`["os", "sys", "subprocess", "pathlib", "shutil"]`) is
  applied in workspace mode too. If the student's project legitimately uses `pathlib` for
  internal file operations, set `import_blacklist` to a list without it. Adding it to
  `import_whitelist` doesn't help, because the blacklist is checked first.
- `import_whitelist` and `import_blacklist` apply to imports in the student's project, setup code
  and the entry point. They don't apply to imports made inside library code, so an allowed library
  such as `numpy` or `pandas` can still load `os` and its other dependencies.
- `sys.path` inside the subprocess is modified to include `workspace_student_dir`, so all
  relative imports within the project work naturally.
- Each call to `workspace_sandbox.query_function` runs in the same subprocess, so module-level
  state (caches, open files) persists across calls within a test — exactly like normal Python.

### Complete Example

**`tests/test_student.py`:**

```python
import pytest

from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.assertions import assert_equal, assert_true
from pytest_prairielearn_grader.fixture import FeedbackFixture, WorkspaceFixture

autograder_config = ConfigObject(
    workspace_mode=True,
    sandbox_timeout=10.0,
    import_whitelist=["math", "statistics"],
)


@pytest.mark.grading_data(name="add() returns correct value", points=3)
def test_add(workspace_sandbox: WorkspaceFixture, feedback: FeedbackFixture) -> None:
    feedback.set_score(0.0)

    response = workspace_sandbox.query_function_raw("calculator.add", 2, 3)
    assert_true(response["status"] != "not_found", msg="calculator.add is not defined")
    feedback.set_score(0.5)

    assert_true(
        response["status"] == "success",
        msg=f"calculator.add raised {response['exception_name']}: {response['exception_message']}",
    )
    feedback.set_score(0.8)

    assert_equal(response["value"], 5, description="calculator.add(2, 3)")
    feedback.set_score(1.0)


@pytest.mark.grading_data(name="divide() raises ValueError on zero", points=2)
def test_divide_guard(workspace_sandbox: WorkspaceFixture) -> None:
    response = workspace_sandbox.query_function_raw("calculator.divide", 10, 0)
    assert_true(response["status"] == "exception", msg="divide() should raise on zero denominator")
    assert_equal(response["exception_name"], "ValueError")


@pytest.mark.grading_data(name="PI_APPROX constant exists", points=1)
def test_constant(workspace_sandbox: WorkspaceFixture) -> None:
    pi = workspace_sandbox.query("calculator.PI_APPROX")
    assert_true(isinstance(pi, float), msg="PI_APPROX should be a float")
    assert_true(abs(pi - 3.14) < 0.01)
```

**Student workspace (`student/calculator.py`):**

```python
PI_APPROX = 3.14159

def add(a, b):
    return a + b

def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
```

## More Examples

To see more examples of what is possible in these test files, look at the test cases in
[this folder](https://github.com/prairielearn/grader-python-v2/tree/main/tests/scenario_root). Each test file is called `scenario.py`.

## Tips and Best Practices

1. **Keep code in the tests**: See [Where Code Belongs](#where-code-belongs).
2. **Use descriptive test names**: The `name` in `@pytest.mark.grading_data` is shown to students.
3. **Use friendly messages that don't give away answers**: Use the assertion helpers with the
   `friendly` output level, and `assert_true` for hidden test cases.
4. **Test incrementally**: Break complex problems into smaller tests with partial credit.
5. **Prefer `parametrize`**: Use `@pytest.mark.parametrize` for several inputs instead of a loop,
   unless the inputs share partial credit.
6. **Control output visibility**: Use `include_stdout_feedback=False` for tests where student output
   would be confusing or reveal answers.
7. **Set appropriate timeouts**: Student code that imports numpy or pandas usually needs a
   `sandbox_timeout` of several seconds.
8. **Use `module_sandbox` sparingly**: Only when you need persistent state across tests.
9. **Watch for `__main__` blocks**: Student code runs with `__name__ == "__main__"`, so code under
   `if __name__ == "__main__":` runs during grading.
10. **Configure security restrictions**: Use `import_whitelist`, `import_blacklist` and
    `builtin_whitelist` to control what modules and functions students can access.
