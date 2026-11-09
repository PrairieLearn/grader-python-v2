import asyncio
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
from copy import deepcopy
from typing import Any

from pytest_prairielearn_grader.json_utils import from_server_json

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
from pytest_prairielearn_grader.utils import StudentFunctionRequest
from pytest_prairielearn_grader.utils import StudentFunctionResponse
from pytest_prairielearn_grader.utils import StudentQueryRequest
from pytest_prairielearn_grader.utils import StudentQueryResponse
from pytest_prairielearn_grader.utils import WorkspaceStartRequest
from pytest_prairielearn_grader.utils import deserialize_object_unsafe
from pytest_prairielearn_grader.utils import get_builtins
from pytest_prairielearn_grader.utils import serialize_object_unsafe

ImportFunction = Callable[[str, Mapping[str, object] | None, Mapping[str, object] | None, Sequence[str] | None, int], types.ModuleType]

# Capture the real built-in import once at module load time, before any patching.
# get_custom_importer must delegate to this to avoid recursion when builtins.__import__
# is later replaced by a workspace_importer in workspace_runner.
_REAL_IMPORT: ImportFunction = builtins.__import__  # type: ignore[assignment]

HOST = "127.0.0.1"  # Loopback address, means "this computer only"


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


async def student_function_runner(
    student_code_vars: dict[str, Any],
    func_name: str,
    timeout: float,
    args_tup: Any,
    kwargs_dict: Any,
    workspace_mode: bool = False,
) -> str:
    """Run a student function and return its StudentFunctionResponse encoded as a JSON string."""
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    execution_error: Exception | None = None
    exception_traceback: str | None = None
    result = None
    timed_out = False

    try:

        def student_function_temp() -> Any:
            if workspace_mode:
                student_function = _resolve_dotted_name(func_name, student_code_vars)
            else:
                student_function = student_code_vars[func_name]
            return student_function(*args_tup, **kwargs_dict)

        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            future = asyncio.get_event_loop().run_in_executor(executor, student_function_temp)
            done, _ = await asyncio.wait({future}, timeout=timeout)
            if done:
                result = future.result()
            else:
                execution_error = asyncio.TimeoutError(f"Function timed out after {timeout} seconds")
                timed_out = True
    except Exception as e:
        execution_error = e
        exception_traceback = traceback.format_exc(limit=-1)

    function_response: StudentFunctionResponse = {
        "status": (
            FunctionStatusCode.SUCCESS
            if execution_error is None
            else FunctionStatusCode.TIMEOUT
            if timed_out
            else FunctionStatusCode.EXCEPTION
        ),
        "value": None,
        "stdout": stdout_capture.getvalue(),
        "stderr": stderr_capture.getvalue(),
        "exception_name": type(execution_error).__name__,
        "exception_message": str(execution_error) if execution_error else None,
        "traceback": exception_traceback,
    }

    try:
        function_response["value"] = to_json(result)
        return json.dumps(function_response)
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
        return json.dumps(not_serializable_response)


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
            exec(compile(source, file_name, "exec"), module.__dict__)
        except Exception as e:
            del self._loaded[name]
            raise ImportError(f"Helper module '{name}' could not be loaded: {type(e).__name__}: {e}") from e
        return module


def get_custom_importer(
    import_whitelist: list[str] | None,
    import_blacklist: list[str] | None,
    workspace_dir: str | None = None,
    helper_modules: _HelperModules | None = None,
) -> ImportFunction:
    """
    Returns a custom import function that restricts imports based on the provided whitelist and
    blacklist.  If a whitelist is provided, only those modules can be imported.

    When *workspace_dir* is given, any module whose top-level package name resolves to a file or
    directory inside that directory is unconditionally allowed, so that student modules can import
    each other without instructors needing to maintain a manual whitelist of their own files.
    Relative imports (level > 0) are always permitted for the same reason.

    Modules in *helper_modules* can be imported without being on the whitelist, and they take
    priority over workspace files with the same name. The grader rejects any that are blacklisted.
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
        if import_blacklist is not None and name in import_blacklist:
            raise ImportError(f"Module '{name}' is blacklisted and cannot be imported.")
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


def find_shadowed_workspace_files(workspace_dir: str) -> list[str]:
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


async def student_code_runner(
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
) -> tuple[dict[str, Any], dict[str, Any], ProcessStartResponse]:
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    execution_error: Exception | None = None
    exception_traceback = None
    local_vars = deepcopy(starting_vars) if starting_vars else {}
    local_vars["__from_server_json"] = from_server_json  # Add the deserialization function to the local variables for setup code to use

    student_code_vars: dict[str, Any] = {}
    student_code_vars["__builtins__"] = get_builtins(builtin_whitelist)

    student_code_vars["__builtins__"]["__name__"] = "__main__"  # Set __name__ to "__main__" to mimic the main module
    student_code_vars["__builtins__"]["__import__"] = get_custom_importer(
        import_whitelist,
        import_blacklist,
        helper_modules=None if helper_modules is None else _HelperModules(helper_modules, student_code_vars["__builtins__"]),
    )

    try:
        # First, execute the setup code if provided
        if setup_code:
            # Compile the setup code
            code_setup = compile(setup_code, "<setup>", "exec")
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(executor, exec, code_setup, student_code_vars, local_vars),
                    timeout=timeout,
                )

    except asyncio.TimeoutError:
        execution_error = asyncio.TimeoutError("Setup code execution timed out")
        # TODO need to create a different message for setup code errors. This should result
        # in a different error message reported from the test case.
    except Exception as e:
        execution_error = e
        # TODO need to create a different message for setup code errors. This should result
        # in a different error message reported from the test case.

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

    if execution_error is None:
        try:
            # Next, compile student code. Make sure to handle errors in this later
            # TODO have a better filename
            code_setup = compile(student_code, student_file_name, "exec")
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(executor, exec, code_setup, student_code_vars, student_code_vars),
                    timeout=timeout,
                )

        except asyncio.TimeoutError:
            execution_error = asyncio.TimeoutError("Student code execution timed out")
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
    elif isinstance(execution_error, asyncio.TimeoutError):
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


async def workspace_runner(
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
    shadowed_files = find_shadowed_workspace_files(workspace_dir)

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    execution_error: Exception | None = None
    exception_traceback = None
    local_vars = deepcopy(starting_vars) if starting_vars else {}
    local_vars["__from_server_json"] = from_server_json

    if shadowed_files:
        shadowed_error = ImportError(
            f"These names are already used by modules that the grader has loaded: {', '.join(shadowed_files)}. "
            "Rename yours and update any imports that use them."
        )
        start_response: ProcessStartResponse = {
            "status": ProcessStatusCode.EXCEPTION,
            "stdout": "",
            "stderr": "",
            "execution_error": type(shadowed_error).__name__,
            "execution_message": str(shadowed_error),
            "execution_traceback": "",
        }
        return local_vars, {}, start_response

    student_code_vars: dict[str, Any] = {}
    student_code_vars["__builtins__"] = get_builtins(builtin_whitelist)
    student_code_vars["__builtins__"]["__name__"] = "__main__"
    workspace_importer = get_custom_importer(
        import_whitelist,
        import_blacklist,
        workspace_dir,
        helper_modules=None if helper_modules is None else _HelperModules(helper_modules, student_code_vars["__builtins__"]),
    )
    student_code_vars["__builtins__"]["__import__"] = workspace_importer
    # Patch the real builtins.__import__ so that workspace modules loaded via
    # importlib.import_module() (which use the real builtins, not student_code_vars)
    # also go through the same restrictions.  The subprocess is dedicated to one
    # grading session so this global patch is safe.
    builtins.__import__ = workspace_importer  # type: ignore[assignment]

    # Insert workspace_dir at the front of sys.path so imports resolve against it.
    # Use insert(0, ...) to take precedence over any previously added paths.
    if workspace_dir not in sys.path:
        sys.path.insert(0, workspace_dir)

    try:
        if setup_code:
            code_setup = compile(setup_code, "<setup>", "exec")
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(executor, exec, code_setup, student_code_vars, local_vars),
                    timeout=timeout,
                )
    except asyncio.TimeoutError:
        execution_error = asyncio.TimeoutError("Setup code execution timed out")
    except Exception as e:
        execution_error = e

    if names_for_user_list is not None:
        for var_name in names_for_user_list:
            if var_name in local_vars:
                student_code_vars[var_name] = deepcopy(local_vars[var_name])
            elif starting_vars is not None and var_name in starting_vars:
                student_code_vars[var_name] = deepcopy(starting_vars[var_name])

    # Optionally exec an entry-point file at startup (e.g. "main.py") so that
    # module-level side effects in the student's root script are applied.
    if execution_error is None and exec_entry is not None:
        entry_path = pathlib.Path(workspace_dir) / exec_entry
        try:
            entry_source = entry_path.read_text(encoding="utf-8")
            entry_code = compile(entry_source, str(entry_path), "exec")
            populate_linecache(entry_source, str(entry_path))
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(executor, exec, entry_code, student_code_vars, student_code_vars),
                    timeout=timeout,
                )
        except asyncio.TimeoutError:
            execution_error = asyncio.TimeoutError("Entry-point file execution timed out")
        except Exception as e:
            execution_error = e
            exception_traceback = traceback.format_exc(limit=-1)

    if execution_error is None:
        status = ProcessStatusCode.SUCCESS
    elif isinstance(execution_error, asyncio.TimeoutError):
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


def encode_server_failure(message: str) -> bytes:
    response: ServerFailureResponse = {"status": ServerStatusCode.FAILURE, "message": message}
    return (json.dumps(response) + os.linesep).encode()


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """
    Reads lines from stdin asynchronously and responds on stdout.
    Mimics a simple server handling requests.
    """
    # try:
    #     json_message = json.loads(message)
    #     result = await asyncio.wait_for(
    #         asyncio.get_event_loop().run_in_executor(executor, _run_blocking_task, task_payload), timeout=timeout_seconds
    #     )
    #     # Example: send an acknowledgement back
    #     response_message = {"status": "received", "data": json_message}
    #     writer.write(json.dumps(response_message).encode("utf-8") + b"\n")  # Add newline for stream parsing
    #     await writer.drain()
    #     # ------------------------------------

    # except json.JSONDecodeError as e:
    #     error_response = {"status": "error", "message": f"Invalid JSON: {e}"}
    #     writer.write(json.dumps(error_response).encode("utf-8") + b"\n")
    #     await writer.drain()
    # except UnicodeDecodeError as e:
    #     error_response = {"status": "error", "message": f"Invalid UTF-8 encoding: {e}"}
    #     writer.write(json.dumps(error_response).encode("utf-8") + b"\n")
    #     await writer.drain()

    try:
        student_code_vars: None | dict = None
        local_vars: None | dict = None
        workspace_mode: bool = False

        async for line_bytes in reader:
            line = line_bytes.decode().strip()
            if not line:  # Handle empty lines
                continue

            json_message = json.loads(line)

            msg_type = json_message.get("message_type")
            if msg_type == MessageType.START_WORKSPACE:
                ws_json_message: WorkspaceStartRequest = json_message
                workspace_mode = True

                local_vars, student_code_vars, start_response = await workspace_runner(
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

                writer.write((json.dumps(start_response) + os.linesep).encode())

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

                local_vars, student_code_vars, start_response = await student_code_runner(
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
                )

                writer.write((json.dumps(start_response) + os.linesep).encode())

            elif msg_type == MessageType.QUERY_SETUP:
                assert local_vars is not None
                query_setup_json_message: SetupQueryRequest = json_message

                var_to_query = query_setup_json_message["var"]
                if var_to_query in local_vars:
                    setup_query_response: SetupQueryResponse = {
                        "status": QueryStatusCode.SUCCESS,
                        "value_encoded": serialize_object_unsafe(local_vars[var_to_query]),
                    }
                else:
                    setup_query_response = {"status": QueryStatusCode.NOT_FOUND, "value_encoded": ""}

                writer.write((json.dumps(setup_query_response) + os.linesep).encode())

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
                    not_found_response: StudentQueryResponse = {"status": QueryStatusCode.NOT_FOUND, "value": "", "error": None}
                    encoded_query_response = json.dumps(not_found_response)
                else:
                    try:
                        query_response: StudentQueryResponse = {"status": QueryStatusCode.SUCCESS, "value": to_json(value), "error": None}
                        encoded_query_response = json.dumps(query_response)
                    except Exception as e:
                        not_serializable_response: StudentQueryResponse = {
                            "status": QueryStatusCode.NOT_SERIALIZABLE,
                            "value": None,
                            "error": f"Variable '{var_to_query}' has a value of type {type(value).__name__}, "
                            f"which can't be sent back to the grader: {e}",
                        }
                        encoded_query_response = json.dumps(not_serializable_response)

                writer.write((encoded_query_response + os.linesep).encode())

            elif msg_type == MessageType.QUERY_FUNCTION:
                assert student_code_vars is not None
                query_function_json_message: StudentFunctionRequest = json_message

                func_name = query_function_json_message["function_name"]
                args = deserialize_object_unsafe(query_function_json_message["args_encoded"])
                kwargs = deserialize_object_unsafe(query_function_json_message["kwargs_encoded"])
                query_timeout = query_function_json_message["query_timeout"]

                encoded_function_response = await student_function_runner(
                    student_code_vars, func_name, query_timeout, args, kwargs, workspace_mode=workspace_mode
                )

                writer.write((encoded_function_response + os.linesep).encode())

            # TODO handle cases of different payloads
            # The first payload should be student code
            if line.lower() == "exit":
                writer.write(("Goodbye!" + os.linesep).encode())
                await writer.drain()
                break  # Exit the loop and terminate the server

            # Simulate processing a request
            # response = f"Server processed: '{line.upper()}'\n"

            await writer.drain()  # Ensure the response is written to stdout

    except asyncio.CancelledError:
        writer.write(encode_server_failure("Server was cancelled."))
    except asyncio.TimeoutError:
        writer.write(encode_server_failure("Student code timed out."))
    except Exception as e:
        writer.write(encode_server_failure(f"An error occurred: {e}"))
    finally:
        # It's good practice to close transports and writers
        # print("Closing server connections...")
        await writer.drain()  # Ensure all data is sent before closing
        writer.close()
        await writer.wait_closed()  # Wait for the writer to finish closing


async def main():
    """
    Starts the asynchronous socket server.
    """
    # Ensure ProactorEventLoop is used on Windows for robust socket operations
    if sys.platform == "win32":
        try:
            loop = asyncio.ProactorEventLoop()
            asyncio.set_event_loop(loop)
            print("Using ProactorEventLoop on Windows.", file=sys.stderr)
        except NotImplementedError:
            print("ProactorEventLoop not available, continuing with default loop.", file=sys.stderr)

    line_limit = 10 * 1024 * 1024  # 10 MB line limit to handle large messages

    # Start the server, binding to the specified host and port
    server = await asyncio.start_server(handle_client, HOST, 0, limit=line_limit)
    addr = server.sockets[0].getsockname()
    print(f"{addr[0]}, {addr[1]}", flush=True)

    async with server:
        # Run forever, or until the server is explicitly stopped
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
