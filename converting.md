# Converting Questions from the Legacy Python Grader

This guide explains how to convert a PrairieLearn question from the legacy Python autograder
(`prairielearn/grader-python`, with `tests/test.py` and `PLTestCase`) to this pytest grader
(`prairielearn/grader-python-pytest`). It's written so that you can give it to a person or an AI
coding agent and have them do the conversion from start to finish.

[quick_start.md](quick_start.md) shows how to write a question for this grader and documents its
full API. This guide covers only what's specific to converting: what changes, in what order to do
it, and the differences from the legacy grader that are easy to miss.

Converted questions in the PrairieLearn example course are good references:

| Question (under `exampleCourse/questions/demo/`) | Shows                                                                                      |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------ |
| `autograder/python/square`                       | A scalar with a tolerance. It still keeps `x` in `setup_code.py`, unlike the version below |
| `autograder/python/pandas`                       | Checking a DataFrame                                                                       |
| `autograder/python/randomFunctionName`           | `server.py` parameters, `data_json`, partial credit, timeouts                              |
| `autograder/codeEditor`                          | A function question                                                                        |
| `annotated/MarkovChainGroupActivity/*`           | Notebook workspaces, `helper_modules`, `data_files`                                        |

## Where code belongs

Legacy questions often run grading code next to the student's code, in `leading_code.py`,
`trailing_code.py` and `setup_code.py`. Don't carry that over. Follow
[Where Code Belongs](quick_start.md#where-code-belongs), which says where each kind of code goes in
this grader and why. A converted question should usually have only `initial_code.py` and
`test_student.py`, plus `setup_code.py` only when student code needs something from it:

- **`ans.py`**: compute the expected values in the tests.
- **`trailing_code.py`**: call the student's functions from the tests with `query_function`.
- **`leading_code.py`**: move imports and definitions to the starter code, or to `helper_modules`.
- **`setup_code.py`**: move random plain values to `server.py`, fixed values to `starting_vars` and
  values that only tests use to the tests. Keep what's left, such as numpy arrays and blocked
  functions.

Don't change what the student has to write to make this work. If the student's task is to set
variables at the top level, keep it that way, and read the variables with `sandbox.query`. If
students have already submitted to the question, check that removing `leading_code.py` doesn't break
those submissions when they're regraded.

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
| `tests/setup_code.py`    | Move what you can out of it, then delete it or update it. See [Update the setup code](#4-update-the-setup-code).        |
| `tests/leading_code.py`  | Move its code to the starter code or `helper_modules`, and delete it. See [Where code belongs](#where-code-belongs).    |
| `tests/trailing_code.py` | Move its code into the tests and delete it. See [Where code belongs](#where-code-belongs).                              |
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

Here's the `square` question, which asks students to set `x_sq` to the square of a random `x`.
The legacy version has four files in `tests/`:

```python
# tests/setup_code.py
import random

x = random.random()
```

```python
# tests/ans.py
x_sq = x**2
```

```python
# tests/initial_code.py
import numpy as np

x_sq = # fill in this code here...
```

```python
# tests/test.py
class Test(PLTestCaseWithPlot):
    @points(10)
    @name("x_sq")
    def test_0(self):
        if Feedback.check_scalar("x_sq", self.ref.x_sq, self.st.x_sq, accuracy_critical=False):
            Feedback.set_score(1)
        else:
            Feedback.set_score(0)
```

Converted, following [Where code belongs](#where-code-belongs):

- `x` is a plain random value that student code reads, so `server.py` generates it instead of
  `setup_code.py`. `question.html` already lists `x` in
  `<pl-external-grader-variables params-name="names_for_user">`, so student code still gets it.
- The expected value comes from the test, so `ans.py` is deleted.
- The starter code parses, so an unchanged submission gets 0 points with feedback.
- `question.html` changes `file-name="user_code.py"` to `file-name="student_code.py"`, and
  `info.json` changes the image to `prairielearn/grader-python-pytest:lite`.

```python
# server.py
import random


def generate(data):
    data["params"]["x"] = random.random()
```

```python
# tests/initial_code.py
x_sq = 0  # fill in this code here...
```

```python
# tests/test_student.py
import pytest
from pytest_prairielearn_grader.assertions import assert_approx_equal
from pytest_prairielearn_grader.fixture import StudentFixture

pytestmark = pytest.mark.output(level="friendly")


@pytest.mark.grading_data(name="x_sq", points=10)
def test_x_sq(sandbox: StudentFixture, data_json: dict) -> None:
    x = data_json["params"]["x"]
    assert_approx_equal(sandbox.query("x_sq"), x**2, description="x_sq")
```

The converted question has no `setup_code.py`. `x` is now the same in every test and every
regrade of a variant, and `question.html` could show it with `{{params.x}}`.

### API mapping

| Legacy                                             | pytest grader                                                                                                         |
| -------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `class Test(PLTestCase)` with `test_*` methods     | Module-level `test_*` functions that take the `sandbox` fixture                                                       |
| `@points(10)` and `@name("...")`                   | `@pytest.mark.grading_data(name="...", points=10)`                                                                    |
| Tests run in sorted name order                     | Tests run in file order                                                                                               |
| `self.st.x`                                        | `sandbox.query("x")`                                                                                                  |
| `Feedback.call_user(self.st.f, a, b)`              | `sandbox.query_function("f", a, b)`, or `query_function_raw` to inspect exceptions and timeouts                       |
| `self.ref.x` from `ans.py`                         | Compute the expected value in the test                                                                                |
| A setup variable, such as `x` from `setup_code.py` | `sandbox.query_setup("x")`                                                                                            |
| `self.data["params"]["k"]`                         | The `data_json` fixture: `data_json["params"]["k"]`                                                                   |
| `Feedback.set_score(s)`                            | `feedback.set_score(s)` with the `feedback` fixture. See [Scoring](#scoring).                                         |
| `Feedback.add_feedback("...")`                     | `feedback.add_message("...")`                                                                                         |
| `accuracy_critical=True`                           | A failed assertion ends the test. Other tests still run.                                                              |
| `total_iters = 3` and `@not_repeated`              | `@pytest.mark.parametrize` over the inputs, or a loop with partial credit                                             |
| `Feedback.not_allowed`                             | `import_blacklist=["numpy.linalg.inv"]` in the `ConfigObject`. See [Update the setup code](#4-update-the-setup-code). |
| `repeated_setup()`                                 | Not needed: setup code runs again for each sandbox.                                                                   |

### Checks

Replace the `Feedback.check_*` functions with the helpers in `pytest_prairielearn_grader.assertions`,
or with numpy and pandas functions wrapped in `assert_true`:

| Legacy                                      | pytest grader                                                                                                       |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `check_scalar(name, ref, st)`               | `assert_approx_equal(value, expected, description=name)`, keeping `rtol=1e-5, atol=1e-8` unless the test set others |
| Exact comparisons                           | `assert_equal(value, expected, description=name)`                                                                   |
| `call_user` plus a comparison               | `assert_fn_equal(sandbox, "f", args=(...), expected=...)` or `assert_fn_approx_equal`                               |
| `check_numpy_array_allclose(name, ref, st)` | The four [array checks](quick_start.md#hiding-expected-values) on type, dtype, shape and values                     |
| `check_numpy_array_features(name, ref, st)` | The first three of those array checks                                                                               |
| `check_list(name, ref, st, entry_type=T)`   | `assert_true(isinstance(value, list), ...)`, a length check and an `isinstance` check on each entry                 |
| `check_tuple`, `check_dict`                 | `assert_equal`                                                                                                      |
| `check_dataframe(name, ref, st)`            | `pandas.testing.assert_frame_equal(expected, df, check_like=True)`, as in the `pandas` example question             |

Keep `check_scalar`'s default tolerances of `rtol=1e-5, atol=1e-8` unless the legacy test set others.

### Feedback messages

Use `@pytest.mark.output(level=GradingOutputLevel.Friendly)` on each test, as the example questions
do, or `output_level="friendly"` in the `ConfigObject`. At this level the student sees only the
assertion's message.

Follow [Hiding Expected Values](quick_start.md#hiding-expected-values): don't use a bare `assert`
or numpy testing functions, and use `assert_true` for hidden test cases. The comparison helpers show
the expected value, which is fine when the legacy feedback showed it too. Keep the wording of the
legacy feedback where you can, such as `"x is inaccurate"`.

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

First, move what you can out of the setup code, as described in [Where code belongs](#where-code-belongs):

- Values that only tests use go in `test_student.py`.
- Random variables that student code reads go in `server.py`, if they're plain JSON values.
- Fixed variables that student code reads go in `starting_vars`.
- Functions that the setup code blocks, such as `la.inv = not_allowed`, go in `import_blacklist`.

If nothing is left, delete `setup_code.py`. Otherwise, update what's left. Setup code runs inside the sandbox, so some things that worked in the legacy grader don't:

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
  the same test that uses them. Don't compute expected values from random setup
  values at module level.
- **Disallowed functions.** `Feedback.not_allowed` isn't available. Instead of overriding the
  function in setup code, list it in `import_blacklist`, which blocks it however student code
  reaches it. The default blacklist is replaced, so keep its entries:

  ```python
  autograder_config = ConfigObject(
      import_blacklist=["os", "sys", "subprocess", "pathlib", "shutil", "numpy.linalg.inv"],
      sandbox_timeout=15,
  )
  ```

  See [Blocking Functions](quick_start.md#blocking-functions). If the setup code computed a value
  with the blocked function, compute it in the test instead.

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
| Solutions use builtins that aren't defaults, such as `getattr`        | `builtin_whitelist=[...]`. See [Builtin Function Control](quick_start.md#builtin-function-control).                        |
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
  a graded cell. Tag the cells with the notebook's imports `#grade`. Use `leading_code.py` only
  when students already have copies of the notebook that you can't change.
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
- **Restricted builtins.** Student code and setup code get only a default set of builtins. It
  includes common ones such as `sum`, `any` and `super`, but not `getattr`, `hasattr`, `setattr`,
  `vars`, `dir`, `globals`, `open`, `eval` or `exec`. Check the solution and the starter code, and
  add what they use to `builtin_whitelist`. A missing builtin shows up as a `NameError` when you
  test the conversion.
- **Default import blacklist.** `os`, `sys`, `subprocess`, `pathlib` and `shutil` are blocked unless
  you set `import_blacklist`.
- **Syntax errors** make the submission ungradable instead of scoring 0.

## 7. Test the conversion

Test the converted question with the grader image before calling the conversion done, as described
in [Testing Locally](quick_start.md#testing-locally). Run each case in a fresh copy of the layout,
because the image moves files around:

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
