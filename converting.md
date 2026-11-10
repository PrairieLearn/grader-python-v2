# Converting Questions from the Legacy Python Grader

This guide explains how to convert a PrairieLearn question from the legacy Python autograder
(`prairielearn/grader-python`, with `tests/test.py` and `PLTestCase`) to this pytest grader
(`prairielearn/grader-python-pytest`). It's written so that you can give it to a person or an AI
coding agent and have them do the conversion from start to finish.

[quick_start.md](quick_start.md) documents every feature in detail. This guide covers what changes,
in what order to do it, and the differences that are easy to miss.

Converted questions in the PrairieLearn example course are good references:

| Question (under `exampleCourse/questions/demo/`) | Shows                                                         |
| ------------------------------------------------ | ------------------------------------------------------------- |
| `autograder/python/square`                       | `setup_code.py`, `query_setup`, a scalar with a tolerance     |
| `autograder/python/pandas`                       | Checking a DataFrame                                          |
| `autograder/python/randomFunctionName`           | `server.py` parameters, `data_json`, partial credit, timeouts |
| `autograder/codeEditor`                          | A function question                                           |
| `annotated/MarkovChainGroupActivity/*`           | Notebook workspaces, `helper_modules`, `data_files`           |

## 1. Check whether the question can be converted

Read every file in the question, including `info.json`, `question.html`, `server.py` and everything in
`tests/`. Stop and report back instead of converting if the question needs one of these:

- **Plot grading.** `PLTestCaseWithPlot` with tests that read `self.st.plt` or call
  `Feedback.check_plot`. The pytest grader can only grade plots that student code builds with
  `MatplotlibSerializer` and returns from a function (see
  [Testing Matplotlib Plots](quick_start.md#testing-matplotlib-plots)), so the student's task would
  change. `PLTestCaseWithPlot` on its own, with no test that reads the plot, isn't a blocker: use the
  normal conversion.
- **Course libraries.** `externalGradingOptions.serverFilesCourse` or imports of course-wide
  modules. The legacy grader put `/grade/serverFilesCourse` on the import path, and this grader
  doesn't.
- **A custom grader image** or an `entrypoint` in `externalGradingOptions`.
- **Values the sandbox can't send back.** Tests can only receive values that can be serialized:
  numbers, strings, `None`, lists, dicts, numpy arrays and scalars, pandas DataFrames and plots
  built with `MatplotlibSerializer`. A test that needs a student's class instance, generator or
  open file has to be rewritten to call student functions that return plain values. Do that only
  if the student's task stays the same.

## 2. Change the files

| Legacy file              | What to do                                                                                                              |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------- |
| `info.json`              | Change `externalGradingOptions.image`. Keep `timeout` and everything else. See [Choosing an image](#choosing-an-image). |
| `question.html`          | Change the file editor's `file-name` to `student_code.py`, or keep it and set `student_code_pattern`.                   |
| `tests/test.py`          | Replace with `tests/test_student.py`. See [Rewrite the tests](#3-rewrite-the-tests).                                    |
| `tests/ans.py`           | Delete it. Compute expected values in `test_student.py`. Don't leave a reference solution in `tests/`.                  |
| `tests/setup_code.py`    | Keep it if it's needed, and update it. See [Update the setup code](#4-update-the-setup-code).                           |
| `tests/leading_code.py`  | Keep it. It's prepended to the student's code, as before.                                                               |
| `tests/trailing_code.py` | Keep it. It's appended to the student's code, as before.                                                                |
| `tests/initial_code.py`  | Keep it. The grader doesn't read it. Fix starter code that doesn't parse (see below).                                   |
| `server.py`              | Usually unchanged.                                                                                                      |

Other changes:

- **Starter code that doesn't parse.** A submission with a `SyntaxError` is ungradable, so it
  doesn't cost the student an attempt, but the student sees no test results. If `initial_code.py`
  has placeholders like `x = # fill this in`, replace them with something that parses, such as
  `x = 0  # fill this in`, so an unchanged submission gets 0 points with feedback.
- **`<pl-external-grader-variables>`.** Keep these elements. The `names_for_user` list still controls
  which setup variables student code gets. The grader ignores `names_from_user`, which only
  displays the table.
- **The file name.** The grader looks for `student_code*.py` by default, while the legacy grader looked
  for `user_code.py`. Change `file-name="user_code.py"` to `file-name="student_code.py"` in
  `question.html`, or add `student_code_pattern="user_code.py"` to the `ConfigObject`. For workspace
  and notebook questions, set `student_code_pattern` to the graded file's name, such as
  `"Markov-Chains-1.ipynb"`.

### Choosing an image

- `prairielearn/grader-python-pytest:lite` when the student code, setup code and tests use only the
  standard library.
- `prairielearn/grader-python-pytest:latest` for anything else, including numpy, pandas,
  matplotlib, sympy and notebooks.

See [Choosing an Image](quick_start.md#choosing-an-image) for what each includes.

## 3. Rewrite the tests

Each `test_*` method on the legacy `Test` class becomes a `test_*` function in
`tests/test_student.py`. Keep each test's name, points and order, and keep checking the same things
with the same tolerances. Don't make the question easier or harder.

Here's the `square` question before and after:

```python
# Legacy tests/test.py
class Test(PLTestCaseWithPlot):
    @points(10)
    @name("x_sq")
    def test_0(self):
        if Feedback.check_scalar("x_sq", self.ref.x_sq, self.st.x_sq, accuracy_critical=False):
            Feedback.set_score(1)
        else:
            Feedback.set_score(0)
```

```python
# tests/test_student.py
import pytest
from pytest_prairielearn_grader.assertions import assert_approx_equal
from pytest_prairielearn_grader.fixture import StudentFixture
from pytest_prairielearn_grader.utils import GradingOutputLevel


@pytest.mark.output(level=GradingOutputLevel.Friendly)
@pytest.mark.grading_data(name="x_sq", points=10)
def test_x_sq(sandbox: StudentFixture) -> None:
    x = sandbox.query_setup("x")
    assert_approx_equal(sandbox.query("x_sq"), x**2, description="x_sq")
```

### API mapping

| Legacy                                             | pytest grader                                                                                       |
| -------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `class Test(PLTestCase)` with `test_*` methods     | Module-level `test_*` functions that take the `sandbox` fixture                                     |
| `@points(10)` and `@name("...")`                   | `@pytest.mark.grading_data(name="...", points=10)`                                                  |
| Tests run in sorted name order                     | Tests run in file order                                                                             |
| `self.st.x`                                        | `sandbox.query("x")`                                                                                |
| `Feedback.call_user(self.st.f, a, b)`              | `sandbox.query_function("f", a, b)`, or `query_function_raw` to inspect exceptions and timeouts     |
| `self.ref.x` from `ans.py`                         | Compute the expected value in the test                                                              |
| A setup variable, such as `x` from `setup_code.py` | `sandbox.query_setup("x")`                                                                          |
| `self.data["params"]["k"]`                         | The `data_json` fixture: `data_json["params"]["k"]`                                                 |
| `Feedback.set_score(s)`                            | `feedback.set_score(s)` with the `feedback` fixture. See [Scoring](#scoring).                       |
| `Feedback.add_feedback("...")`                     | `feedback.add_message("...")`                                                                       |
| `accuracy_critical=True`                           | A failed assertion ends the test. Other tests still run.                                            |
| `total_iters = 3` and `@not_repeated`              | `@pytest.mark.parametrize` over the inputs, or a loop with partial credit                           |
| `Feedback.not_allowed`                             | Define your own function in `setup_code.py`. See [Update the setup code](#4-update-the-setup-code). |
| `repeated_setup()`                                 | Not needed: setup code runs again for each sandbox.                                                 |

### Checks

Replace the `Feedback.check_*` functions with the helpers in `pytest_prairielearn_grader.assertions`,
or with numpy and pandas functions wrapped in `assert_true`:

| Legacy                                      | pytest grader                                                                                                       |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `check_scalar(name, ref, st)`               | `assert_approx_equal(value, expected, description=name)`, keeping `rtol=1e-5, atol=1e-8` unless the test set others |
| Exact comparisons                           | `assert_equal(value, expected, description=name)`                                                                   |
| `call_user` plus a comparison               | `assert_fn_equal(sandbox, "f", args=(...), expected=...)` or `assert_fn_approx_equal`                               |
| `check_numpy_array_allclose(name, ref, st)` | The four array checks below                                                                                         |
| `check_numpy_array_features(name, ref, st)` | The first three array checks below                                                                                  |
| `check_list(name, ref, st, entry_type=T)`   | `assert_true(isinstance(value, list), ...)`, a length check and an `isinstance` check on each entry                 |
| `check_tuple`, `check_dict`                 | `assert_equal`                                                                                                      |
| `check_dataframe(name, ref, st)`            | `pandas.testing.assert_frame_equal(expected, df, check_like=True)`, as in the `pandas` example question             |

For a numpy array, check the type, dtype, shape and values in that order, so that each failure has a
clear message and a wrong shape doesn't reach `np.allclose`:

```python
value = sandbox.query("x")
assert_true(isinstance(value, np.ndarray), msg="x should be a numpy array")
assert_true(np.issubdtype(value.dtype, np.number), msg="x should contain numbers")
assert_true(value.shape == expected.shape, msg=f"x should have shape {expected.shape}")
assert_true(np.allclose(value, expected, rtol=1e-5, atol=1e-8), msg="x is inaccurate")
```

`assert_approx_equal` is for scalars. Don't use it for arrays.

### Feedback messages

Use `@pytest.mark.output(level=GradingOutputLevel.Friendly)` on each test, as the example questions
do, or `output_level="friendly"` in the `ConfigObject`. At this level the student sees only the
assertion's message.

Pick assertions with that in mind:

- **Bare `assert`.** Don't use it in tests. pytest rewrites it, so the student sees
  `assert 6 == 12345` and the fixture's `repr` along with your message, which gives away the
  expected value.
- **numpy and pandas assertions.** `np.testing.assert_allclose` and similar include both arrays in
  their messages. Use `assert_true(np.allclose(...), msg=...)` instead.
- **`assert_equal` and the other comparison helpers.** These show the expected value. That's fine
  when the legacy feedback showed it too, or when the test's inputs are visible to the student. For
  hidden test cases, use `assert_true` with a message that doesn't include the answer.
- **Wording.** Keep the wording of the legacy feedback where you can, such as `"x is inaccurate"`.

### Scoring

- A test that finishes without failing gets full points, even if it never calls `feedback.set_score`.
- A test that fails gets the last score it set with `feedback.set_score`, or 0. Call `set_score`
  after each check that earns partial credit.
- `feedback.set_score_final(s)` sets the score even if the test then fails.
- The legacy pattern of `if check: set_score(1) else: set_score(0)` becomes a plain assertion.

### Querying

- `query` and `query_function` raise `NameError` if the student didn't define the name, which fails
  the test with a message that says so. You don't need to check this yourself.
- Each call to `query_function` has a 1 second timeout by default. Pass `query_timeout=` for slower
  functions.
- When a test calls a student function several times, use `query_function_raw` and stop after the
  first `"timeout"` status: see the `randomFunctionName` example question.

## 4. Update the setup code

Setup code runs inside the sandbox, so some things that worked in the legacy grader don't:

- **Parameters.** `data` isn't defined. Use `__data_params`, which is `data["params"]`. Values that
  `server.py` stored with `pl.to_json` arrive still encoded: decode them with
  `__from_server_json(__data_params["A"])`. The `prairielearn` package isn't available.
- **Restrictions.** Setup code runs with the same builtins and import rules as student code. For
  example, it can't call `open` or import `os`. To read a data file, list it in `data_files` and use
  a library function such as `np.loadtxt`.
- **Variables for the student.** Student code only gets the setup variables named in
  `names_for_user`. This list usually comes from `<pl-external-grader-variables
params-name="names_for_user">` in `question.html`. If the question defines these names somewhere
  else, or not at all, set `names_for_user=[...]` in the `ConfigObject`.
- **Fresh values per test.** The `sandbox` fixture runs setup code and student code again for each
  test, so random values in setup code change between tests. Read them with `sandbox.query_setup` in
  the same test that uses them, as `square` does. Don't compute expected values from random setup
  values at module level.
- **Disallowed functions.** `Feedback` isn't available. Define a replacement in setup code:

  ```python
  import numpy.linalg as la


  def not_allowed(*args, **kwargs):
      raise RuntimeError("Usage of this function is not allowed in this question.")


  la.inv = not_allowed
  ```

If the setup code only defined values that tests need, and student code doesn't use them, move that
code into `test_student.py` and delete `setup_code.py`.

## 5. Configure the grader

Put a `ConfigObject` named `autograder_config` at the top of `test_student.py` when the defaults
don't fit:

```python
from pytest_prairielearn_grader import ConfigObject

autograder_config = ConfigObject(
    student_code_pattern="Markov-Chains-1.ipynb",
    notebook_cell_tag="#grade",
    # Importing numpy in student code can take longer than the default timeout.
    sandbox_timeout=15,
)
```

When a `ConfigObject` is present, the module-level `sandbox_timeout` variable and the
`@pytest.mark.sandbox_timeout` marker are ignored.

| Situation                                                             | Setting                                                                                                                    |
| --------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Student or setup code imports numpy, pandas or other large libraries  | `sandbox_timeout=15`. The default of 1 second covers starting the student's code.                                          |
| The graded file isn't `student_code*.py`                              | `student_code_pattern="..."`                                                                                               |
| A notebook where only some cells should run                           | `notebook_cell_tag="#grade"`                                                                                               |
| Student code or `leading_code.py` imports a module from `tests/`      | `helper_modules=["module_name"]`. See [Helper Modules](quick_start.md#helper-modules).                                     |
| Student code or `leading_code.py` reads a file from `tests/`          | `data_files=["file.txt"]`, and read it in tests with the `tests_dir` fixture. See [Data Files](quick_start.md#data-files). |
| Student code imports `os`, `sys`, `subprocess`, `pathlib` or `shutil` | `import_blacklist=[...]` without that module. These are blocked by default.                                                |
| The legacy setup code blocked imports or builtins                     | `import_whitelist`, `import_blacklist` or `builtin_whitelist`                                                              |
| A multi-file workspace project with `.py` files                       | `workspace_mode=True`. See [Workspace Grading](quick_start.md#workspace-grading).                                          |

`test_student.py` itself can't import other files from `tests/`. Put helper code for the tests in
`test_student.py`, and read data files through `tests_dir`.

## 6. Notebook questions

For questions where students submit a Jupyter notebook from a workspace:

- Set `student_code_pattern` to the notebook's name from `workspaceOptions.gradedFiles`.
- Legacy notebook questions grade only the cells that start with `#grade`. Keep that with
  `notebook_cell_tag="#grade"`. Without it, every code cell runs, including plots and scratch work.
- Set `sandbox_timeout=15` if the notebook imports numpy or similar libraries.
- Notebook questions use the normal `sandbox` fixture, not `workspace_mode`.
- The grader runs the graded cells as a script, so anything a graded cell needs must be defined in
  a graded cell or in `leading_code.py`.
- If the notebook reads a data file, list it in `data_files`. If the notebook imports a `.py` file
  that's in the workspace, copy that file into `tests/` and list it in `helper_modules`.

## Behavior differences

These differences from the legacy grader are easy to miss:

- **`__name__`.** Student code runs with `__name__ == "__main__"`, so code under
  `if __name__ == "__main__":` runs during grading. The legacy grader skipped it. If the starter code
  has such a block, check that running it during grading is harmless. A `leading_code.py` that only
  sets `__name__ = "__main__"` is no longer needed.
- **No reference run.** `ans.py` isn't run. Expected values come from the test code.
- **Setup code runs for each test**, and so does the student's code. Output that student code prints
  at the top level appears in each test's feedback, unless the test sets
  `include_stdout_feedback=False` in `grading_data`.
- **Default import blacklist.** `os`, `sys`, `subprocess`, `pathlib` and `shutil` are blocked unless
  you set `import_blacklist`.
- **Syntax errors** make the submission ungradable instead of scoring 0.

## 7. Test the conversion

Test the converted question with the grader image before calling the conversion done. Run each case
in a fresh copy of the layout, because the image moves files around:

```bash
mkdir -p grade/tests grade/student grade/data
cp -R path/to/question/tests/. grade/tests/
cp solution.py grade/student/student_code.py
echo '{"params": {}}' > grade/data/data.json
docker run --rm -v "$PWD/grade:/grade" prairielearn/grader-python-pytest:latest
cat grade/results/results.json
```

- **`data.json`.** Put in `params` whatever the question's `server.py` and elements would set. In
  particular, `<pl-external-grader-variables params-name="names_for_user">` sets
  `params["names_for_user"]` to a list of `{"name": ..., "description": ..., "type": ...}` objects.
  Without it, student code doesn't get the setup variables.
- **Cases to run.** At least a correct solution, which should get full points, the unchanged starter
  code, which should get 0 without crashing the grader, and one wrong answer for each test. Compare
  the scores with what the legacy grader would give.
- **Messages.** Read `message` for each test in `results.json`, and check that hidden test cases don't
  reveal their expected values.
- **Notebooks.** Use the solution notebook as the submission, with the file name from `gradedFiles`.

Finally, test the question in PrairieLearn itself, with a local PrairieLearn server and the example
or course repository. A person usually does this step. If you couldn't, say so when you report back.

## 8. Report back

When you're done, report:

- Which files you changed, added and deleted.
- Any check whose behavior changed, such as a different tolerance or message, and why.
- The cases you ran and their scores.
- Anything you couldn't convert or test.
