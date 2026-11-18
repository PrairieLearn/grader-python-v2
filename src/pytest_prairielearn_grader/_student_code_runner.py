import builtins
import concurrent.futures
import importlib
import io
import json
import linecache
import os
import pathlib
import sys
import traceback
import types
from collections.abc import Callable
from collections.abc import Mapping
from collections.abc import Sequence
from contextlib import redirect_stderr
from contextlib import redirect_stdout
from contextlib import suppress
from copy import deepcopy
from multiprocessing.connection import Connection
from typing import Any

from pytest_prairielearn_grader.json_utils import from_server_json
from pytest_prairielearn_grader.json_utils import is_json_transportable

# TODO make it so that other files in this package cannot import from this one
# ask Gemini how to do it
from pytest_prairielearn_grader.json_utils import to_json
from pytest_prairielearn_grader.utils import FunctionStatusCode
from pytest_prairielearn_grader.utils import MessageType
from pytest_prairielearn_grader.utils import ProcessStartRequest
from pytest_prairielearn_grader.utils import ProcessStartResponse
from pytest_prairielearn_grader.utils import ProcessStatusCode
from pytest_prairielearn_grader.utils import QueryStatusCode
from pytest_prairielearn_grader.utils import ServerFailureResponse
from pytest_prairielearn_grader.utils import ServerStatusCode
from pytest_prairielearn_grader.utils import SetupQueryRequest
from pytest_prairielearn_grader.utils import SetupQueryResponse
from pytest_prairielearn_grader.utils import SetupSnapshotEntry
from pytest_prairielearn_grader.utils import SetupSnapshotMessage
from pytest_prairielearn_grader.utils import StudentFunctionRequest
from pytest_prairielearn_grader.utils import StudentFunctionResponse
from pytest_prairielearn_grader.utils import StudentQueryRequest
from pytest_prairielearn_grader.utils import StudentQueryResponse
from pytest_prairielearn_grader.utils import WorkspaceStartRequest
from pytest_prairielearn_grader.utils import deserialize_object_unsafe
from pytest_prairielearn_grader.utils import drop_privileges
from pytest_prairielearn_grader.utils import get_builtins
from pytest_prairielearn_grader.utils import serialize_object_unsafe

ImportFunction = Callable[[str, Mapping[str, object] | None, Mapping[str, object] | None, Sequence[str] | None, int], types.ModuleType]

# Capture the real built-in import once at module load time, before any patching.
# get_custom_importer must delegate to this to avoid recursion when builtins.__import__
# is later replaced by a workspace_importer in workspace_runner.
_REAL_IMPORT: ImportFunction = builtins.__import__  # type: ignore[assignment]


# Global ThreadPoolExecutor for CPU-bound tasks
# It's good practice to create this once and reuse it.
# The number of workers should ideally be around the number of CPU cores.
executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)


def populate_linecache(contents: str, fname: str) -> None:
    """
    TODO do what's in this file here
    https://github.com/PrairieLearn/PrairieLearn/commit/28c1f0bfb3792c950e5df30061469bfaf0ca199f
    """
    linecache.cache[fname] = (
        len(contents),
        None,
        [line + os.linesep for line in contents.splitlines()],
        fname,
    )


def _resolve_dotted_name(name: str, student_code_vars: dict[str, Any]) -> Any:
    """
    Resolves a name that may be a dotted module path (e.g. 'models.classifier.predict').

    For dotted names, splits on the last '.' to get a module path and attribute name,
    then imports the module and retrieves the attribute.  This uses the normal Python
    import machinery, so relative imports, __init__.py, and package structure all work
    as expected.

    For flat names, falls back to looking up the name in student_code_vars (the
    namespace populated by setup_code and direct exec).
    """
    if "." in name:
        module_path, attr_name = name.rsplit(".", 1)
        mod = importlib.import_module(module_path)
        return getattr(mod, attr_name)
    return student_code_vars[name]


class FunctionNotFoundError(Exception):
    """The requested function doesn't exist. Only the lookup raises this, never the student's call."""


def _look_up_function(name: str, student_code_vars: dict[str, Any], workspace_mode: bool) -> Any:
    """
    Find a student function by name, raising FunctionNotFoundError if it doesn't exist.

    In workspace mode, importing a dotted name's module runs student code. If that code fails, the
    error isn't caught here unless the failure is that the requested module itself doesn't exist,
    so a student module that exists but has a bad import is reported as an exception.
    """
    not_found = FunctionNotFoundError(f"Function '{name}' wasn't found in the student code")
    if workspace_mode and "." in name:
        module_path, attr_name = name.rsplit(".", 1)
        try:
            module = importlib.import_module(module_path)
        except ModuleNotFoundError as e:
            if e.name is not None and (module_path == e.name or module_path.startswith(f"{e.name}.")):
                raise not_found from e
            raise
        try:
            return getattr(module, attr_name)
        except AttributeError as e:
            raise not_found from e
    if name not in student_code_vars:
        raise not_found
    return student_code_vars[name]


def student_function_runner(
    student_code_vars: dict[str, Any],
    func_name: str,
    timeout: float,
    args_tup: Any,
    kwargs_dict: Any,
    workspace_mode: bool = False,
) -> StudentFunctionResponse:
    """Run a student function and return its StudentFunctionResponse."""
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    execution_error: Exception | None = None
    exception_traceback: str | None = None
    result = None
    timed_out = False
    function_not_found = False

    try:

        def student_function_temp() -> Any:
            student_function = _look_up_function(func_name, student_code_vars, workspace_mode)
            return student_function(*args_tup, **kwargs_dict)

        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            future = executor.submit(student_function_temp)
            try:
                result = future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                execution_error = TimeoutError(f"Function timed out after {timeout} seconds")
                timed_out = True
    except FunctionNotFoundError as e:
        execution_error = NameError(str(e))
        function_not_found = True
    except Exception as e:
        execution_error = e
        exception_traceback = traceback.format_exc(limit=-1)

    function_response: StudentFunctionResponse = {
        "status": (
            FunctionStatusCode.SUCCESS
            if execution_error is None
            else FunctionStatusCode.TIMEOUT
            if timed_out
            else FunctionStatusCode.NOT_FOUND
            if function_not_found
            else FunctionStatusCode.EXCEPTION
        ),
        "value": None,
        "stdout": stdout_capture.getvalue(),
        "stderr": stderr_capture.getvalue(),
        "exception_name": type(execution_error).__name__,
        "exception_message": str(execution_error) if execution_error else None,
        "traceback": exception_traceback,
    }

    # On any execution error the call produced no value, so leave it as None.
    if execution_error is not None:
        return function_response

    try:
        # The value is sent back to the grader as a JSON string so that only JSON data, never a
        # student-controlled object, crosses the pipe into the grader process. json.dumps also
        # raises here for a value that can't be represented, which drives the NOT_SERIALIZABLE path.
        function_response["value"] = json.dumps(to_json(result))
        return function_response
    except Exception as e:
        not_serializable_response: StudentFunctionResponse = {
            "status": FunctionStatusCode.NOT_SERIALIZABLE,
            "value": None,
            "stdout": function_response["stdout"],
            "stderr": function_response["stderr"],
            "exception_name": type(e).__name__,
            "exception_message": (
                f"Function '{func_name}' returned a value of type {type(result).__name__}, which can't be sent back to the grader: {e}"
            ),
            "traceback": None,
        }
        return not_serializable_response


def encode_setup_variables(local_vars: dict[str, Any]) -> dict[str, SetupSnapshotEntry]:
    """
    Dill-encode the setup variables that JSON can't represent, such as functions.

    Other variables aren't encoded here, so large data doesn't slow down starting the sandbox.
    They're sent as JSON if they're queried. Each variable is encoded on its own so that one
    value dill can't handle only fails a query for that value, not the whole sandbox.
    """
    encoded: dict[str, SetupSnapshotEntry] = {}
    for name, value in local_vars.items():
        if is_json_transportable(value):
            continue
        try:
            # recurse leaves out globals a function doesn't use, which can include large data.
            encoded[name] = {
                "status": QueryStatusCode.SUCCESS,
                "value_encoded": serialize_object_unsafe(value, recurse=True),
                "error": None,
            }
        except Exception as e:
            encoded[name] = {"status": QueryStatusCode.NOT_SERIALIZABLE, "value_encoded": "", "error": f"{type(e).__name__}: {e}"}
    return encoded


def _find_blacklisted(name: str, fromlist: Sequence[str], import_blacklist: list[str]) -> str | None:
    """
    Returns the module that an import would load in spite of the blacklist, or None.

    A blacklisted entry also covers its submodules, so "os" blocks `import os.path`, and
    "matplotlib.pyplot" blocks `from matplotlib import pyplot` but not `import matplotlib`.
    """
    names = [name, *(f"{name}.{item}" for item in fromlist if item != "*")]
    for candidate in names:
        for entry in import_blacklist:
            if candidate == entry or candidate.startswith(entry + "."):
                return candidate
    return None


def _block_blacklisted_functions(import_blacklist: list[str] | None) -> None:
    """
    Replaces each blacklisted function, such as "numpy.linalg.inv", with one that raises.

    The importer only sees import statements, so on its own it can't stop `np.linalg.inv(A)`.
    Modules are shared by everything in the sandbox, so this covers every way student code can
    reach the function through its module. Entries whose module isn't installed, or that name a
    module or a value that isn't callable, are left to the importer.
    """
    for entry in import_blacklist or []:
        module_name, _, attribute = entry.rpartition(".")
        if not module_name:
            continue
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        value = getattr(module, attribute, None)
        if value is None or isinstance(value, types.ModuleType) or not callable(value):
            continue
        setattr(module, attribute, _make_blocked_function(entry))


def _make_blocked_function(entry: str) -> Callable[..., Any]:
    def blocked(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError(f"'{entry}' is blacklisted and cannot be used.")

    return blocked


SERVER_DATA_PACKAGE = "pytest_prairielearn_grader"
SERVER_DATA_MODULE = f"{SERVER_DATA_PACKAGE}.server_data"


class ServerDataImport:
    """
    Gives setup code its own copy of the server_data module, holding this sandbox's params.

    The copy is kept out of sys.modules, and it can only be imported until the setup code
    finishes, so student code can't read the params.
    """

    def __init__(self, params: dict[str, Any]) -> None:
        self.module = types.ModuleType(SERVER_DATA_MODULE)
        self.module.params = params  # type: ignore[attr-defined]
        self.module.from_server_json = from_server_json  # type: ignore[attr-defined]
        # `import pytest_prairielearn_grader.server_data` and `from pytest_prairielearn_grader
        # import server_data` both get the top-level package back from __import__.
        self.package = types.ModuleType(SERVER_DATA_PACKAGE)
        self.package.server_data = self.module  # type: ignore[attr-defined]
        self.available = True

    def matches(self, name: str, fromlist: Sequence[str]) -> bool:
        return name == SERVER_DATA_MODULE or (name == SERVER_DATA_PACKAGE and "server_data" in fromlist)

    def load(self, name: str, fromlist: Sequence[str]) -> types.ModuleType:
        if not self.available:
            raise ImportError(f"Module '{SERVER_DATA_MODULE}' can only be imported by setup code.")
        return self.module if name == SERVER_DATA_MODULE and fromlist else self.package


class _HelperModules:
    """
    Loads the modules named by the helper_modules setting from the source sent by the grader.

    They're kept out of sys.modules so that only the sandbox's importer can find them, and they
    run with the given builtins, so importing one doesn't give student code any wider access.
    """

    def __init__(self, sources: dict[str, str], module_builtins: dict[str, Any]) -> None:
        self._sources = sources
        self._module_builtins = module_builtins
        self._loaded: dict[str, types.ModuleType] = {}

    def __contains__(self, name: str) -> bool:
        return name in self._sources

    def load(self, name: str) -> types.ModuleType:
        if name in self._loaded:
            return self._loaded[name]

        source = self._sources[name]
        file_name = f"{name}.py"
        populate_linecache(source, file_name)

        module = types.ModuleType(name)
        module.__dict__["__builtins__"] = self._module_builtins
        # Add it before running it so that helper modules can import each other, as in sys.modules.
        self._loaded[name] = module
        try:
            exec(compile(source, file_name, "exec"), module.__dict__)  # noqa: S102
        except Exception as e:
            del self._loaded[name]
            raise ImportError(f"Helper module '{name}' could not be loaded: {type(e).__name__}: {e}") from e
        return module


def get_custom_importer(
    import_whitelist: list[str] | None,
    import_blacklist: list[str] | None,
    workspace_dir: str | None = None,
    helper_modules: _HelperModules | None = None,
    server_data: ServerDataImport | None = None,
) -> ImportFunction:
    """
    Returns a custom import function that restricts imports based on the provided whitelist and
    blacklist.  If a whitelist is provided, only those modules can be imported.

    When *workspace_dir* is given, any module whose top-level package name resolves to a file or
    directory inside that directory is unconditionally allowed, so that student modules can import
    each other without instructors needing to maintain a manual whitelist of their own files.
    Relative imports (level > 0) are always permitted for the same reason. Imports made by library
    modules outside that directory aren't restricted, so an allowed library can load what it needs.

    Modules in *helper_modules* can be imported without being on the whitelist, and they take
    priority over workspace files with the same name. The grader rejects any that are blacklisted.

    *server_data* provides the server_data module to setup code, whatever the whitelist and
    blacklist say.
    """

    original_import = _REAL_IMPORT

    # Pre-compute the workspace directory string at factory time (before this importer is
    # installed into builtins.__import__).  Doing pathlib.Path() or os.path operations
    # inside custom_import itself would trigger re-entrant calls: Python 3.12 pathlib
    # lazy-imports ntpath/posixpath on first use, which would call custom_import again
    # and cause infinite RecursionError.  Using a plain str and os.path functions (which
    # are loaded as part of the 'os' module and never need to re-import anything) is safe.
    _ws_str: str | None = str(pathlib.Path(workspace_dir)) if workspace_dir is not None else None

    def custom_import(
        name: str,
        globals: Mapping[str, object] | None = None,
        locals: Mapping[str, object] | None = None,
        fromlist: Sequence[str] | None = None,
        level: int = 0,
    ) -> types.ModuleType:
        fl = fromlist or ()
        # Relative imports are always intra-package and allowed.
        if level > 0:
            return original_import(name, globals, locals, fl, level)

        # In workspace mode this importer replaces builtins.__import__ for the whole process, so it
        # also sees imports made inside libraries, such as numpy's own `import os`. The rules are
        # for student code, so let through imports made by a module file outside the workspace.
        # Code with no module file, such as setup code and the entry point, is still restricted.
        # The caller's frame is used rather than the globals argument, because some libraries call
        # __import__ directly without one (pandas does for its dependencies).
        if _ws_str is not None:
            importer_file = sys._getframe(1).f_globals.get("__file__")
            if isinstance(importer_file, str) and not importer_file.startswith(_ws_str + os.sep):
                return original_import(name, globals, locals, fl, level)

        if server_data is not None and server_data.matches(name, fl):
            return server_data.load(name, fl)

        if helper_modules is not None and name in helper_modules:
            return helper_modules.load(name)

        # Workspace-local modules are always importable regardless of whitelist/blacklist.
        # A module is considered local if its top-level package maps to a file or directory
        # directly inside workspace_dir.
        if _ws_str is not None:
            top_level = name.split(".")[0]
            if os.path.isfile(os.path.join(_ws_str, top_level + ".py")) or os.path.isdir(os.path.join(_ws_str, top_level)):
                return original_import(name, globals, locals, fl, level)

        # Apply blacklist / whitelist to external imports.
        if import_blacklist is not None and (blocked := _find_blacklisted(name, fl, import_blacklist)) is not None:
            raise ImportError(f"Module '{blocked}' is blacklisted and cannot be imported.")
        elif (
            (import_whitelist is not None and name in import_whitelist)
            or name.startswith("_")  # Allow Python internal/private modules (_io, _abc, _collections, etc.)
            or import_whitelist is None
        ):
            return original_import(name, globals, locals, fl, level)
        else:
            # Forbid other imports
            raise ImportError(f"Module '{name}' is not allowed to be imported.")

    return custom_import


def _module_is_from_dir(module: types.ModuleType, directory: str) -> bool:
    """Whether *module* was loaded from a file or package inside *directory*."""
    locations: list[str] = []
    module_file = getattr(module, "__file__", None)
    if isinstance(module_file, str):
        locations.append(module_file)
    module_path = getattr(module, "__path__", None)
    if module_path is not None:
        try:
            locations.extend(str(p) for p in module_path)
        except TypeError:
            pass
    for location in locations:
        real_location = os.path.realpath(location)
        if real_location == directory or real_location.startswith(directory + os.sep):
            return True
    return False


def _find_shadowed_workspace_files(workspace_dir: str) -> list[str]:
    """
    Return the top-level ``.py`` files and folders in *workspace_dir* whose names match a module
    that this process has already loaded from somewhere else.

    Python reuses an already loaded module on import, so the student's file would be silently
    ignored.  Folders are listed with a trailing slash.
    """
    real_dir = os.path.realpath(workspace_dir)
    clashes: list[str] = []
    for entry in sorted(os.listdir(real_dir)):
        path = os.path.join(real_dir, entry)
        if entry.endswith(".py") and os.path.isfile(path):
            name, label = entry[:-3], entry
        elif os.path.isdir(path):
            name, label = entry, entry + "/"
        else:
            continue
        module = sys.modules.get(name)
        if module is not None and not _module_is_from_dir(module, real_dir):
            clashes.append(label)
    return clashes


def _find_helper_name_clashes(workspace_dir: str, helper_modules: dict[str, str] | None) -> list[str]:
    """Return the student's files and folders that an import of a helper module would silently replace."""
    clashes: list[str] = []
    for name in helper_modules or {}:
        if os.path.isdir(os.path.join(workspace_dir, name)):
            clashes.append(f"{name}/")
        elif os.path.isfile(os.path.join(workspace_dir, f"{name}.py")):
            clashes.append(f"{name}.py")
    return clashes


def _run_sandbox(
    *,
    setup_code: str | None,
    timeout: float,
    import_whitelist: list[str] | None,
    import_blacklist: list[str] | None,
    starting_vars: dict[str, Any] | None,
    builtin_whitelist: list[str] | None,
    names_for_user_list: list[str] | None,
    helper_modules: dict[str, str] | None,
    workspace_dir: str | None,
    load_main: Callable[[], tuple[str, str]] | None,
    main_timeout_message: str,
    on_setup_complete: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], ProcessStartResponse]:
    """
    Shared implementation behind student_code_runner and workspace_runner.

    Runs the setup code, injects the names_for_user variables, and then runs a main code object:
    the student submission for student mode, or the workspace entry-point file for workspace mode.
    *load_main*, called inside the capture/timeout region, returns that code's (source, file_name);
    pass None to skip the main step. When *workspace_dir* is given, the importer also replaces the
    real builtins.__import__ and the directory is put at the front of sys.path, so that student
    modules loaded via importlib.import_module() go through the same restrictions and resolve
    against the workspace.

    *on_setup_complete*, if given, is called with the setup namespace after setup code finishes and
    before any main/student code runs. It must complete before the main step: it's what lets the
    grader capture a snapshot of setup values that nothing the student defined or changed can reach.
    """
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    execution_error: Exception | None = None
    exception_traceback = None
    local_vars = deepcopy(starting_vars) if starting_vars else {}
    local_vars["__from_server_json"] = from_server_json  # Add the deserialization function to the local variables for setup code to use

    student_code_vars: dict[str, Any] = {}
    student_code_vars["__builtins__"] = get_builtins(builtin_whitelist)
    student_code_vars["__builtins__"]["__name__"] = "__main__"  # Set __name__ to "__main__" to mimic the main module
    server_data = ServerDataImport(local_vars.get("__data_params", {}))
    importer = get_custom_importer(
        import_whitelist,
        import_blacklist,
        workspace_dir,
        helper_modules=None if helper_modules is None else _HelperModules(helper_modules, student_code_vars["__builtins__"]),
        server_data=server_data,
    )
    _block_blacklisted_functions(import_blacklist)
    student_code_vars["__builtins__"]["__import__"] = importer
    if workspace_dir is not None:
        # Patch the real builtins.__import__ so that workspace modules loaded via
        # importlib.import_module() (which use the real builtins, not student_code_vars)
        # also go through the same restrictions.  The subprocess is dedicated to one
        # grading session so this global patch is safe.
        builtins.__import__ = importer  # type: ignore[assignment]
        # Insert workspace_dir at the front of sys.path so imports resolve against it.
        # Use insert(0, ...) to take precedence over any previously added paths.
        if workspace_dir not in sys.path:
            sys.path.insert(0, workspace_dir)

    try:
        # First, execute the setup code if provided
        if setup_code:
            # Compile the setup code
            code_setup = compile(setup_code, "<setup>", "exec")
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                executor.submit(exec, code_setup, student_code_vars, local_vars).result(timeout=timeout)

    except concurrent.futures.TimeoutError:
        execution_error = TimeoutError("Setup code execution timed out")
        # TODO need to create a different message for setup code errors. This should result
        # in a different error message reported from the test case.
    except Exception as e:
        execution_error = e
        # TODO need to create a different message for setup code errors. This should result
        # in a different error message reported from the test case.

    server_data.available = False

    # Only inject variables that are explicitly listed in names_for_user_list
    # This prevents accidental variable leaking from setup_code or starting_vars
    if names_for_user_list is not None:
        for var_name in names_for_user_list:
            if var_name in local_vars:
                # NOTE I think there might be issues with security with deepcopying certain
                # objects. If needed, we can prevent leaks here through serialization.
                student_code_vars[var_name] = deepcopy(local_vars[var_name])
            elif starting_vars is not None and var_name in starting_vars:
                # If not in local_vars (setup_code), try getting from starting_vars
                student_code_vars[var_name] = deepcopy(starting_vars[var_name])

    # This has to finish before any student code runs: it's what guarantees the dill data the
    # grader deserializes contains nothing the student defined or changed.
    if on_setup_complete is not None:
        on_setup_complete(local_vars if execution_error is None else {})

    if execution_error is None and load_main is not None:
        try:
            # Compile and run the main code (student submission or workspace entry point).
            main_source, main_file_name = load_main()
            main_code = compile(main_source, main_file_name, "exec")
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                executor.submit(exec, main_code, student_code_vars, student_code_vars).result(timeout=timeout)

        except concurrent.futures.TimeoutError:
            execution_error = TimeoutError(main_timeout_message)
        except Exception as e:
            execution_error = e
            # TODO this traceback only shows the last line with the exception.
            # Would be better if we could give the full traceback within the student code
            # for example, if the student code calls a function that raises an exception,
            # we should show the full self-contained traceback including the function call.
            exception_traceback = traceback.format_exc(limit=-1)

    # Determine the status based on the type of error
    if execution_error is None:
        status = ProcessStatusCode.SUCCESS
    elif isinstance(execution_error, TimeoutError):
        status = ProcessStatusCode.TIMEOUT
    else:
        status = ProcessStatusCode.EXCEPTION

    result_dict: ProcessStartResponse = {
        "status": status,
        "stdout": stdout_capture.getvalue(),
        "stderr": stderr_capture.getvalue(),
        "execution_error": type(execution_error).__name__ if execution_error else None,
        "execution_message": str(execution_error) if execution_error else None,
        "execution_traceback": str(exception_traceback),
    }

    return local_vars, student_code_vars, result_dict


def student_code_runner(
    setup_code: str | None,
    student_code: str,
    student_file_name: str,
    timeout: float,
    import_whitelist: list[str] | None,
    import_blacklist: list[str] | None,
    starting_vars: dict[str, Any] | None,
    builtin_whitelist: list[str] | None,
    names_for_user_list: list[str] | None,
    helper_modules: dict[str, str] | None,
    on_setup_complete: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], ProcessStartResponse]:
    return _run_sandbox(
        setup_code=setup_code,
        timeout=timeout,
        import_whitelist=import_whitelist,
        import_blacklist=import_blacklist,
        starting_vars=starting_vars,
        builtin_whitelist=builtin_whitelist,
        names_for_user_list=names_for_user_list,
        helper_modules=helper_modules,
        workspace_dir=None,
        load_main=lambda: (student_code, student_file_name),
        main_timeout_message="Student code execution timed out",
        on_setup_complete=on_setup_complete,
    )


def workspace_runner(
    workspace_dir: str,
    exec_entry: str | None,
    setup_code: str | None,
    timeout: float,
    import_whitelist: list[str] | None,
    import_blacklist: list[str] | None,
    starting_vars: dict[str, Any] | None,
    builtin_whitelist: list[str] | None,
    names_for_user_list: list[str] | None,
    helper_modules: dict[str, str] | None,
) -> tuple[dict[str, Any], dict[str, Any], ProcessStartResponse]:
    """
    Sets up a workspace sandbox by inserting workspace_dir at the front of sys.path
    so that student modules can be imported via their dotted names.  Optionally
    executes an entry-point file (exec_entry) and runs setup_code exactly as the
    regular student_code_runner does.
    """
    # Check before anything else runs, so the result depends only on what the sandbox loads
    # for itself and not on what the setup code or the student's code imports.
    helper_clashes = _find_helper_name_clashes(workspace_dir, helper_modules)
    shadowed_files = [f for f in _find_shadowed_workspace_files(workspace_dir) if f not in helper_clashes]

    if helper_clashes or shadowed_files:
        local_vars = deepcopy(starting_vars) if starting_vars else {}
        local_vars["__from_server_json"] = from_server_json
        reasons = []
        if helper_clashes:
            reasons.append(f"These names are reserved for modules that this question provides: {', '.join(helper_clashes)}.")
        if shadowed_files:
            reasons.append(f"These names are already used by modules that the grader has loaded: {', '.join(shadowed_files)}.")
        clash_error = ImportError(" ".join(reasons) + " Rename yours and update any imports that use them.")
        start_response: ProcessStartResponse = {
            "status": ProcessStatusCode.EXCEPTION,
            "stdout": "",
            "stderr": "",
            "execution_error": type(clash_error).__name__,
            "execution_message": str(clash_error),
            "execution_traceback": "",
        }
        return local_vars, {}, start_response

    # Optionally exec an entry-point file at startup (e.g. "main.py") so that
    # module-level side effects in the student's root script are applied.
    load_main: Callable[[], tuple[str, str]] | None = None
    if exec_entry is not None:
        entry = exec_entry

        def load_entry() -> tuple[str, str]:
            entry_path = pathlib.Path(workspace_dir) / entry
            entry_source = entry_path.read_text(encoding="utf-8")
            populate_linecache(entry_source, str(entry_path))
            return entry_source, str(entry_path)

        load_main = load_entry

    return _run_sandbox(
        setup_code=setup_code,
        timeout=timeout,
        import_whitelist=import_whitelist,
        import_blacklist=import_blacklist,
        starting_vars=starting_vars,
        builtin_whitelist=builtin_whitelist,
        names_for_user_list=names_for_user_list,
        helper_modules=helper_modules,
        workspace_dir=workspace_dir,
        load_main=load_main,
        main_timeout_message="Entry-point file execution timed out",
    )


def _serve(conn: Connection, worker_username: str | None, data_files_dir: str | None) -> None:
    """
    Entry point for the sandbox child process. Drops privileges, then serves requests over the pipe.

    The grader spawns this with a multiprocessing.Process and holds the other end of the pipe. Each
    request is a message dict received with conn.recv(); the response dict is sent with conn.send().
    The loop ends when the grader closes its end (conn.recv() raises EOFError) or the process is
    terminated.
    """
    # multiprocessing.Process has no preexec_fn, so the privilege drop is the first thing the child
    # does, before it reads or runs anything on the grader's behalf.
    if worker_username is not None and sys.platform != "win32":
        drop_privileges(worker_username)
    # With data files, the sandbox runs in a folder holding copies of them so student code can read
    # them by relative path. subprocess set this with cwd=...; multiprocessing has no such option.
    if data_files_dir is not None:
        os.chdir(data_files_dir)
    # Student code runs on a worker thread with no display, so matplotlib must not pick a GUI backend.
    os.environ.setdefault("MPLBACKEND", "Agg")

    student_code_vars: None | dict = None
    local_vars: None | dict = None
    workspace_mode: bool = False

    try:
        while True:
            try:
                json_message = conn.recv()
            except EOFError:
                break

            msg_type = json_message.get("message_type")
            if msg_type == MessageType.START_WORKSPACE:
                ws_json_message: WorkspaceStartRequest = json_message
                workspace_mode = True

                local_vars, student_code_vars, start_response = workspace_runner(
                    workspace_dir=ws_json_message["workspace_dir"],
                    exec_entry=ws_json_message["exec_entry"],
                    setup_code=ws_json_message["setup_code"],
                    timeout=ws_json_message["initialization_timeout"],
                    import_whitelist=ws_json_message["import_whitelist"],
                    import_blacklist=ws_json_message["import_blacklist"],
                    starting_vars=ws_json_message["starting_vars"],
                    builtin_whitelist=ws_json_message["builtin_whitelist"],
                    names_for_user_list=ws_json_message["names_for_user_list"],
                    helper_modules=ws_json_message["helper_modules"],
                )

                conn.send(start_response)

            elif msg_type == MessageType.START:
                start_json_message: ProcessStartRequest = json_message
                # Execute the student code for the first time and load
                # variables into the student_code_vars dictionary
                student_code = start_json_message["student_code"]
                student_file_name = start_json_message["student_file_name"]
                setup_code = start_json_message["setup_code"]
                initialization_timeout = start_json_message["initialization_timeout"]
                import_whitelist = start_json_message["import_whitelist"]
                import_blacklist = start_json_message["import_blacklist"]
                starting_vars = start_json_message["starting_vars"]
                builtin_whitelist = start_json_message["builtin_whitelist"]
                names_for_user_list = start_json_message["names_for_user_list"]

                populate_linecache(student_code, student_file_name)

                def send_setup_snapshot(setup_vars: dict[str, Any]) -> None:
                    snapshot: SetupSnapshotMessage = {"message_type": "setup_snapshot", "variables": encode_setup_variables(setup_vars)}
                    conn.send(snapshot)
                    # Wait for the grader to acknowledge before student code runs. Only the ack proves
                    # the grader has the whole snapshot; a recv failure means it's gone, so stop.
                    conn.recv()

                local_vars, student_code_vars, start_response = student_code_runner(
                    setup_code=setup_code,
                    student_code=student_code,
                    student_file_name=student_file_name,
                    timeout=initialization_timeout,
                    import_whitelist=import_whitelist,
                    import_blacklist=import_blacklist,
                    starting_vars=starting_vars,
                    builtin_whitelist=builtin_whitelist,
                    names_for_user_list=names_for_user_list,
                    helper_modules=start_json_message["helper_modules"],
                    on_setup_complete=send_setup_snapshot,
                )

                conn.send(start_response)

            elif msg_type == MessageType.QUERY_SETUP:
                assert local_vars is not None
                query_setup_json_message: SetupQueryRequest = json_message

                var_to_query = query_setup_json_message["var"]
                # Student code may have run by now, so a setup value is only ever sent as JSON here;
                # the grader never deserializes dill from this response. Values JSON can't represent
                # come from the snapshot taken before student code ran, not from this path.
                if var_to_query not in local_vars:
                    setup_query_response: SetupQueryResponse = {"status": QueryStatusCode.NOT_FOUND, "value": None, "error": None}
                else:
                    try:
                        setup_query_response = {
                            "status": QueryStatusCode.SUCCESS,
                            "value": json.dumps(to_json(local_vars[var_to_query])),
                            "error": None,
                        }
                    except Exception as e:
                        setup_query_response = {
                            "status": QueryStatusCode.NOT_SERIALIZABLE,
                            "value": None,
                            "error": f"{type(e).__name__}: {e}",
                        }

                conn.send(setup_query_response)

            elif msg_type == MessageType.QUERY:
                assert student_code_vars is not None
                query_json_message: StudentQueryRequest = json_message

                var_to_query = query_json_message["var"]

                try:
                    if workspace_mode and "." in var_to_query:
                        value = _resolve_dotted_name(var_to_query, student_code_vars)
                    elif var_to_query in student_code_vars:
                        value = student_code_vars[var_to_query]
                    else:
                        raise KeyError(var_to_query)

                except (KeyError, AttributeError, ImportError):
                    query_response: StudentQueryResponse = {"status": QueryStatusCode.NOT_FOUND, "value": "", "error": None}
                else:
                    try:
                        # Send the value as a JSON string: see student_function_runner for why.
                        query_response = {"status": QueryStatusCode.SUCCESS, "value": json.dumps(to_json(value)), "error": None}
                    except Exception as e:
                        query_response = {
                            "status": QueryStatusCode.NOT_SERIALIZABLE,
                            "value": None,
                            "error": f"Variable '{var_to_query}' has a value of type {type(value).__name__}, "
                            f"which can't be sent back to the grader: {e}",
                        }

                conn.send(query_response)

            elif msg_type == MessageType.QUERY_FUNCTION:
                assert student_code_vars is not None
                query_function_json_message: StudentFunctionRequest = json_message

                func_name = query_function_json_message["function_name"]
                args = deserialize_object_unsafe(query_function_json_message["args_encoded"])
                kwargs = deserialize_object_unsafe(query_function_json_message["kwargs_encoded"])
                query_timeout = query_function_json_message["query_timeout"]

                function_response = student_function_runner(
                    student_code_vars, func_name, query_timeout, args, kwargs, workspace_mode=workspace_mode
                )

                conn.send(function_response)

    except Exception as e:
        # Report an unexpected server-level failure (e.g. a message that couldn't be unpickled) so
        # the grader can explain it, then stop; the grader closes its end on the next query. The send
        # itself can fail if the grader already closed the pipe, and there's nothing left to do then.
        failure: ServerFailureResponse = {"status": ServerStatusCode.FAILURE, "message": f"An error occurred: {e}"}
        with suppress(Exception):
            conn.send(failure)
    finally:
        conn.close()
