import base64
import json
import logging
import multiprocessing
import os
import shutil
import signal
import stat
import sys
import tempfile
from collections.abc import Callable
from multiprocessing.connection import Connection
from multiprocessing.context import SpawnProcess
from pathlib import Path
from typing import Any
from typing import NamedTuple

from ._student_code_runner import _serve
from .json_utils import from_json
from .utils import FunctionStatusCode
from .utils import MessageType
from .utils import ProcessStartRequest
from .utils import ProcessStartResponse
from .utils import ProcessStatusCode
from .utils import QueryStatusCode
from .utils import ServerStatusCode
from .utils import SetupQueryRequest
from .utils import SetupQueryResponse
from .utils import StudentFunctionRequest
from .utils import StudentFunctionResponse
from .utils import StudentQueryRequest
from .utils import StudentQueryResponse
from .utils import WorkspaceStartRequest
from .utils import deserialize_object_unsafe
from .utils import format_call
from .utils import serialize_object_unsafe

DataFixture = dict[str, Any]

# The sandbox runs in a child process started with the "spawn" method. spawn gives the child a fresh
# interpreter instead of forking the grader's memory, which would break the sandbox's isolation.
_MP_CONTEXT = multiprocessing.get_context("spawn")
DEFAULT_TIMEOUT = 1.0
# Extra time to wait for the start response, so that the sandbox's own
# initialization timeout is reported instead of racing against the read timeout.
START_RESPONSE_GRACE = 0.5
# Seconds to wait for the sandbox's process to exit after it closes the connection, to read why it stopped.
STOPPED_PROCESS_WAIT = 1.0

# Modes for the data files folder (see _make_data_files_dir). Everyone can read the files and list the
# folders, and nobody can change them; only the owner (root, in the Docker image) can make them writable again.
_READ_ONLY_FILE_MODE = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH  # r--r--r--
_READ_ONLY_DIR_MODE = _READ_ONLY_FILE_MODE | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH  # r-xr-xr-x
# Lets the owner delete the folder's contents at cleanup.
_OWNER_WRITABLE_DIR_MODE = _READ_ONLY_DIR_MODE | stat.S_IWUSR  # rwxr-xr-x

logger = logging.getLogger(__name__)


class SandboxStopped(RuntimeError):
    """
    Raised by a query on a sandbox where an earlier query timed out.

    The student code may still send the reply to the call that timed out, and a later query would
    read it as its own answer. So after a timeout, the sandbox refuses all further queries.
    """

    timed_out_call: str

    def __init__(self, timed_out_call: str) -> None:
        super().__init__(f"This check didn't run because {timed_out_call}.")
        self.timed_out_call = timed_out_call


def _extract_notebook_code(notebook_path: Path, cell_tag: str | None = None) -> str:
    """Extract Python source code from a Jupyter notebook (.ipynb) file.

    Args:
        notebook_path: Path to the ``.ipynb`` file.
        cell_tag: When provided, only code cells whose first non-empty line
            starts with this string are included.  When ``None`` all code cells
            are included.

    Returns:
        A single Python source string containing all selected cell contents
        joined by double newlines.

    Raises:
        ImportError: If ``nbformat`` is not installed.
    """
    try:
        import nbformat  # type: ignore[import-untyped]  # noqa: PLC0415
    except ImportError:
        raise ImportError(
            "nbformat is required for Jupyter notebook grading support. Install it with: pip install 'pytest-prairielearn-grader[notebook]'"
        ) from None

    with notebook_path.open(encoding="utf-8-sig") as f:
        nb = nbformat.read(f, as_version=4)

    code_parts: list[str] = []
    for cell in nb.cells:
        if cell.cell_type != "code":
            continue
        source: str = cell.source
        if cell_tag is not None:
            lines = source.strip().splitlines()
            if not lines or not lines[0].strip().startswith(cell_tag):
                continue
        code_parts.append(source)

    return "\n\n".join(code_parts)


def _make_data_files_dir(data_files: dict[str, Path]) -> Path:
    """Copy each data file to its relative path in a new folder that only its owner can change.

    The folder is made by the grader process, so in the Docker image it's owned by root and the
    sandbox user can read the copies but not change, add or remove anything.
    """
    root = Path(tempfile.mkdtemp(prefix="pl-data-files-"))
    try:
        for relative_path, source in data_files.items():
            destination = root / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            destination.chmod(_READ_ONLY_FILE_MODE)
        for directory in [root, *(path for path in root.rglob("*") if path.is_dir())]:
            directory.chmod(_READ_ONLY_DIR_MODE)
    except BaseException:
        _remove_data_files_dir(root)
        raise
    return root


def _remove_data_files_dir(root: Path) -> None:
    for directory in [root, *(path for path in root.rglob("*") if path.is_dir())]:
        directory.chmod(_OWNER_WRITABLE_DIR_MODE)
    shutil.rmtree(root, ignore_errors=True)


class StudentFiles(NamedTuple):
    leading_file: Path
    trailing_file: Path
    student_code_file: Path
    setup_code_file: Path


class FeedbackFixture:
    """
    A fixture to handle feedback from the student code.
    """

    test_id: str
    messages: list[str]
    images: list[dict[str, str]]
    score: float | None
    final_score_override: bool

    def __init__(self, test_id: str) -> None:
        self.test_id = test_id
        self.messages = []
        self.images = []
        self.score = None
        self.final_score_override = False

    def add_message(self, message: str) -> None:
        self.messages.append(message)

    def add_image(self, image: Any, *, label: str | None = None) -> None:
        """
        Shows an image with this test's results, such as a plot queried from student code.

        `image` is a matplotlib Figure or Axes, or the bytes of a PNG file. PrairieLearn limits the
        whole results file to 1 MB, so add only a few images.
        """
        if isinstance(image, bytes):
            png = image
        else:
            # matplotlib is an optional dependency, so only import it when a plot is added.
            from pytest_prairielearn_grader.matplotlib_json import plot_to_png  # noqa: PLC0415

            png = plot_to_png(image)

        entry = {"url": "data:image/png;base64," + base64.b64encode(png).decode("ascii")}
        if label is not None:
            entry["label"] = label
        self.images.append(entry)

    def set_score(self, score: float) -> None:
        self.score = score

    def set_score_final(self, score: float) -> None:
        """
        Sets the final score for the test. This should be called at the end of the test.
        """
        if self.score is not None:
            raise RuntimeError("Final score has already been set.")

        # TODO maybe change this to assert the score is 1? Then it will fail if the score is not 1.
        # Will maintain invariant that score should be 1 if all tests pass.
        self.score = score
        self.final_score_override = True

    def to_dict(self) -> dict:
        result: dict[str, Any] = {
            "test_id": self.test_id,
            "message": os.linesep.join(self.messages),
            "points_frac": self.score,
        }
        if self.images:
            result["images"] = self.images
        return result


class _SandboxBase:
    """
    Shared child-process/pipe plumbing used by StudentFixture and WorkspaceFixture.
    Not intended to be instantiated directly.
    """

    process: SpawnProcess | None
    _conn: Connection | None
    _read_timeout: float
    import_whitelist: list[str] | None
    import_blacklist: list[str] | None
    starting_vars: dict[str, Any] | None
    builtin_whitelist: list[str] | None
    names_for_user_list: list[str] | None
    worker_username: str | None
    helper_modules: dict[str, str] | None
    data_files: dict[str, Path] | None
    _data_files_dir: Path | None
    _accumulated_stdout: list[str]
    _server_failure: str | None
    _timed_out_call: str | None

    def __init__(
        self,
        import_whitelist: list[str] | None,
        import_blacklist: list[str] | None,
        starting_vars: dict[str, Any] | None,
        builtin_whitelist: list[str] | None,
        names_for_user_list: list[str] | None,
        worker_username: str | None,
        helper_modules: dict[str, str] | None = None,
        data_files: dict[str, Path] | None = None,
    ) -> None:
        self.import_whitelist = import_whitelist
        self.import_blacklist = import_blacklist
        self.starting_vars = starting_vars
        self.builtin_whitelist = builtin_whitelist
        self.names_for_user_list = names_for_user_list
        self.worker_username = worker_username
        self.helper_modules = helper_modules
        self.data_files = data_files
        self._data_files_dir = None
        self.process = None
        self._conn = None
        self._read_timeout = DEFAULT_TIMEOUT
        self._accumulated_stdout = []
        self._server_failure = None
        self._timed_out_call = None

    def _start_server(self, initialization_timeout: float, build_start_message: Callable[[], Any]) -> ProcessStartResponse:
        """Spawn the child process, send the start message it builds, and read the start response."""
        self._start_subprocess()
        json_message = build_start_message()
        self._send_json_object(json_message)
        return self._read_start_response(initialization_timeout)

    def _assert_process_running(self) -> None:
        assert self.process is not None, "Sandbox process is not running. Please start it first."
        if self.process.exitcode is not None:
            raise RuntimeError(f"Sandbox process terminated with code {self.process.exitcode}.")

    def _send_json_object(self, json_object: Any) -> None:
        assert self._conn is not None, "Pipe is not connected. Please start the sandbox server first."
        self._conn.send(json_object)

    def _recv_message(self) -> Any:
        """Read one message from the pipe, waiting up to the current read timeout for it to arrive."""
        assert self._conn is not None, "Pipe is not connected. Please start the sandbox server first."
        if not self._conn.poll(self._read_timeout):
            raise TimeoutError("Pipe read timed out.")
        try:
            return self._conn.recv()
        except EOFError as e:
            # The child closed its end without sending a reply, i.e. its process stopped.
            self._server_failure = self._describe_stopped_sandbox()
            self._assert_no_server_failure()
            raise RuntimeError(self._server_failure) from e  # unreachable: the assert above raises

    def _describe_stopped_sandbox(self) -> str:
        """Say why the sandbox closed the connection, from how its process exited."""
        return_code = None
        if self.process is not None:
            self.process.join(timeout=STOPPED_PROCESS_WAIT)
            return_code = self.process.exitcode
        # The kernel's out-of-memory killer, and container memory limits, stop a process with SIGKILL.
        if sys.platform != "win32" and return_code == -signal.SIGKILL:
            return "The sandbox running your code was killed, probably because your code used too much memory."
        if return_code is not None:
            return f"The sandbox running your code stopped unexpectedly with exit code {return_code}."
        return "The sandbox running your code stopped unexpectedly."

    def _assert_no_server_failure(self) -> None:
        if self._server_failure is not None:
            raise RuntimeError(self._server_failure)
        if self._timed_out_call is not None:
            raise SandboxStopped(self._timed_out_call)

    def _read_query_response(self) -> Any:
        """Read a response to a query, raising a clear error if the server failed and closed the connection."""
        data = self._recv_message()
        if data.get("status") == ServerStatusCode.FAILURE:
            self._server_failure = f"The sandbox stopped unexpectedly, so later queries won't work: {data['message']}"
            self._assert_no_server_failure()
        # A successful query or function call sends its value as a JSON string; decode it back to a
        # structure so the response matches what callers (and from_json) expect.
        if data.get("status") == QueryStatusCode.SUCCESS:
            data["value"] = json.loads(data["value"])
        return data

    def _start_subprocess(self) -> None:
        """Spawn the runner child process and store it in ``self.process``."""
        # With data files, the sandbox starts in a folder holding copies of them, so student code can
        # read them by relative path. Without them, the starting folder is left as it was.
        if self.data_files is not None:
            self._data_files_dir = _make_data_files_dir(self.data_files)

        parent_conn, child_conn = _MP_CONTEXT.Pipe()
        data_files_dir = None if self._data_files_dir is None else str(self._data_files_dir)
        self.process = _MP_CONTEXT.Process(
            target=_serve,
            args=(child_conn, self.worker_username, data_files_dir),
            daemon=True,
        )
        self.process.start()
        # Close the child's end in the grader so that if the child process dies, the grader's recv
        # sees EOF instead of blocking on a handle it still holds open itself.
        child_conn.close()
        self._conn = parent_conn
        self._assert_process_running()

    def _read_start_response(self, initialization_timeout: float) -> ProcessStartResponse:
        """Read and return the ProcessStartResponse sent after the start message."""
        self._read_timeout = initialization_timeout + START_RESPONSE_GRACE
        try:
            res: ProcessStartResponse = self._recv_message()
            if res.get("stdout"):
                self._accumulated_stdout.append(res["stdout"])
        except Exception as e:
            res = {
                "status": ProcessStatusCode.NO_RESPONSE,
                "execution_error": type(e).__name__,
                "execution_message": str(e),
                "execution_traceback": "",
                "stdout": "",
                "stderr": "",
            }
        return res

    def query_raw(self, var_to_query: str, *, query_timeout: float = DEFAULT_TIMEOUT) -> StudentQueryResponse:
        self._assert_no_server_failure()
        self._assert_process_running()
        json_message = StudentQueryRequest(message_type=MessageType.QUERY, var=var_to_query, query_timeout=query_timeout)
        self._read_timeout = query_timeout
        self._send_json_object(json_message)
        try:
            data: StudentQueryResponse = self._read_query_response()
        except TimeoutError as error:
            self._timed_out_call = f"the query for '{var_to_query}' timed out after {query_timeout} seconds"
            raise TimeoutError(f"The query for '{var_to_query}' timed out after {query_timeout} seconds.") from error
        return data

    def query(self, var_to_query: str, *, query_timeout: float = DEFAULT_TIMEOUT) -> Any:
        """Query a variable from the student sandbox by name."""
        response = self.query_raw(var_to_query, query_timeout=query_timeout)
        match response["status"]:
            case QueryStatusCode.NOT_FOUND:
                raise NameError(f"Query for '{var_to_query}' failed")
            case QueryStatusCode.NOT_SERIALIZABLE:
                raise RuntimeError(response["error"])
        return from_json(response["value"])

    def query_function_raw(
        self, function_name: str, *args: Any, query_timeout: float = DEFAULT_TIMEOUT, **kwargs: Any
    ) -> StudentFunctionResponse:
        """Call a student function and return its protocol response.

        A socket timeout is returned as ``FunctionStatusCode.TIMEOUT`` rather
        than raised. After a timeout, every later query on this sandbox raises
        SandboxStopped, because the student process may still write the
        timed-out request's response.

        Raises a RuntimeError if the sandbox server failed, for example because it
        couldn't load the arguments. The sandbox can't be used after that.
        """
        self._assert_no_server_failure()
        json_message = StudentFunctionRequest(
            message_type=MessageType.QUERY_FUNCTION,
            function_name=function_name,
            args_encoded=serialize_object_unsafe(args),
            kwargs_encoded=serialize_object_unsafe(kwargs),
            query_timeout=query_timeout,
        )
        self._read_timeout = query_timeout
        self._send_json_object(json_message)
        try:
            data: StudentFunctionResponse = self._read_query_response()
        except TimeoutError as error:
            data = {
                "status": FunctionStatusCode.TIMEOUT,
                "value": None,
                "stdout": "",
                "stderr": "",
                "exception_name": type(error).__name__,
                "exception_message": None,
                "traceback": None,
            }
        # The student process also times out the call, and its reply can arrive before the socket
        # read times out. Either way, the function may still be running, so stop the sandbox.
        if data["status"] == FunctionStatusCode.TIMEOUT:
            self._timed_out_call = f"{format_call(function_name, args, kwargs)} timed out after {query_timeout} seconds"
            data["exception_message"] = f"{self._timed_out_call}."
        if data.get("stdout"):
            self._accumulated_stdout.append(data["stdout"])
        return data

    def query_function(self, function_name: str, *args: Any, query_timeout: float = DEFAULT_TIMEOUT, **kwargs: Any) -> Any:
        """Call a function in the student sandbox and return its value."""
        response = self.query_function_raw(function_name, *args, query_timeout=query_timeout, **kwargs)
        match response["status"]:
            case FunctionStatusCode.EXCEPTION:
                call = format_call(function_name, args, kwargs)
                raise RuntimeError(f"{call} raised {response['exception_name']}: {response['exception_message']}\n{response['traceback']}")
            case FunctionStatusCode.TIMEOUT:
                raise TimeoutError(response["exception_message"])
            case FunctionStatusCode.NOT_FOUND:
                raise NameError(response["exception_message"])
            case FunctionStatusCode.NOT_SERIALIZABLE:
                raise RuntimeError(response["exception_message"])
        return from_json(response["value"])

    def get_accumulated_stdout(self) -> str:
        """Return all stdout captured from function calls made through this fixture."""
        return "".join(self._accumulated_stdout)

    def _cleanup(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        if self.process is not None:
            self.process.terminate()
            self.process.join()
            self.process = None
        if self._data_files_dir is not None:
            _remove_data_files_dir(self._data_files_dir)
            self._data_files_dir = None


class StudentFixture(_SandboxBase):
    leading_file: Path
    trailing_file: Path
    student_code_file: Path
    setup_code_file: Path

    def __init__(
        self,
        file_names: StudentFiles,
        import_whitelist: list[str] | None,
        import_blacklist: list[str] | None,
        starting_vars: dict[str, Any] | None,
        builtin_whitelist: list[str] | None,
        names_for_user_list: list[str] | None,
        worker_username: str | None,
        notebook_cell_tag: str | None = None,
        helper_modules: dict[str, str] | None = None,
        data_files: dict[str, Path] | None = None,
    ) -> None:
        super().__init__(
            import_whitelist,
            import_blacklist,
            starting_vars,
            builtin_whitelist,
            names_for_user_list,
            worker_username,
            helper_modules=helper_modules,
            data_files=data_files,
        )
        self.leading_file = file_names.leading_file
        self.trailing_file = file_names.trailing_file
        self.student_code_file = file_names.student_code_file
        self.setup_code_file = file_names.setup_code_file
        self.notebook_cell_tag = notebook_cell_tag

    def start_student_code_server(self, *, initialization_timeout: float = DEFAULT_TIMEOUT) -> ProcessStartResponse:
        if self.worker_username is not None:
            logger.debug(f"Starting student code server with worker username: {self.worker_username}")
        else:
            logger.debug("Starting student code server without dropping privileges.")

        def build_start_message() -> ProcessStartRequest:
            student_code = ""
            if self.leading_file.is_file():
                student_code += self.leading_file.read_text(encoding="utf-8")
                student_code += os.linesep
            if self.student_code_file.is_file():
                if self.student_code_file.suffix.lower() == ".ipynb":
                    student_code += _extract_notebook_code(self.student_code_file, self.notebook_cell_tag)
                else:
                    student_code += self.student_code_file.read_text(encoding="utf-8")
            if self.trailing_file.is_file():
                student_code += os.linesep
                student_code += self.trailing_file.read_text(encoding="utf-8")

            setup_code = None
            if self.setup_code_file.is_file():
                setup_code = self.setup_code_file.read_text(encoding="utf-8")

            # TODO make this a shared type
            return ProcessStartRequest(
                message_type=MessageType.START,
                student_code=student_code,
                student_file_name=str(self.student_code_file),
                setup_code=setup_code,
                initialization_timeout=initialization_timeout,
                import_whitelist=self.import_whitelist,
                import_blacklist=self.import_blacklist,
                starting_vars=self.starting_vars,
                builtin_whitelist=self.builtin_whitelist,
                names_for_user_list=self.names_for_user_list,
                helper_modules=self.helper_modules,
            )

        return self._start_server(initialization_timeout, build_start_message)

    def query_setup_raw(self, var_to_query: str) -> SetupQueryResponse:
        self._assert_no_server_failure()
        self._assert_process_running()
        json_message: SetupQueryRequest = {"message_type": MessageType.QUERY_SETUP, "var": var_to_query}
        self._send_json_object(json_message)
        data: SetupQueryResponse = self._recv_message()
        return data

    def query_setup(self, var_to_query: str) -> Any:
        """Queries a variable from the setup code and returns its value."""
        response = self.query_setup_raw(var_to_query)
        if response["status"] == "not_found":
            raise NameError(f"Query for setup variable '{var_to_query}' failed")
        return deserialize_object_unsafe(response["value_encoded"])

    def student_source(self) -> str:
        """Return the source code the student submitted.

        Use this to inspect the submission itself, for example parsing it with
        :mod:`ast` to check how a result was produced. For a ``.py`` submission
        this is the file's text. For a notebook submission it is the code from
        the graded cells, the same code that runs in the sandbox, selected by
        ``notebook_cell_tag`` when one is set.

        This is only the student's file, not any ``leading_code.py`` or
        ``trailing_code.py`` the question adds around it.
        """
        if not self.student_code_file.is_file():
            raise FileNotFoundError(f"No student submission found at {self.student_code_file}")
        if self.student_code_file.suffix.lower() == ".ipynb":
            return _extract_notebook_code(self.student_code_file, self.notebook_cell_tag)
        return self.student_code_file.read_text(encoding="utf-8")

    # TODO add functions that let instructors use the student fixture
    # use the stuff pete set up here: https://github.com/reteps/pytest-autograder-prototype
    def __repr__(self) -> str:
        return f"StudentFixture(leading_file={self.leading_file}, trailing_file={self.trailing_file}, student_code_file={self.student_code_file})"


class WorkspaceFixture(_SandboxBase):
    """
    Fixture for grading workspace-based student projects.

    In workspace mode the student submission is a multi-file Python project
    rooted at *workspace_dir*.  That directory is added to ``sys.path`` inside
    the sandbox subprocess so that standard Python import machinery works
    transparently.

    Tests interact with the student's project using dotted module paths:

    .. code-block:: python

        result = workspace_sandbox.query_function("models.classifier.predict", X)
        value  = workspace_sandbox.query("utils.EPSILON")

    Flat (non-dotted) names fall back to variables injected via ``setup_code``
    or ``names_for_user``, exactly as in the regular :class:`StudentFixture`.
    """

    workspace_dir: Path
    setup_code_file: Path
    exec_entry: str | None

    def __init__(
        self,
        workspace_dir: Path,
        setup_code_file: Path,
        import_whitelist: list[str] | None,
        import_blacklist: list[str] | None,
        starting_vars: dict[str, Any] | None,
        builtin_whitelist: list[str] | None,
        names_for_user_list: list[str] | None,
        worker_username: str | None,
        exec_entry: str | None = None,
        helper_modules: dict[str, str] | None = None,
        data_files: dict[str, Path] | None = None,
    ) -> None:
        super().__init__(
            import_whitelist,
            import_blacklist,
            starting_vars,
            builtin_whitelist,
            names_for_user_list,
            worker_username,
            helper_modules=helper_modules,
            data_files=data_files,
        )
        self.workspace_dir = workspace_dir
        self.setup_code_file = setup_code_file
        self.exec_entry = exec_entry

    def start_workspace_server(self, *, initialization_timeout: float = DEFAULT_TIMEOUT) -> ProcessStartResponse:
        """Start the sandbox subprocess and initialise the workspace."""

        def build_start_message() -> WorkspaceStartRequest:
            setup_code: str | None = None
            if self.setup_code_file.is_file():
                setup_code = self.setup_code_file.read_text(encoding="utf-8")

            return WorkspaceStartRequest(
                message_type=MessageType.START_WORKSPACE,
                workspace_dir=str(self.workspace_dir),
                exec_entry=self.exec_entry,
                setup_code=setup_code,
                initialization_timeout=initialization_timeout,
                import_whitelist=self.import_whitelist,
                import_blacklist=self.import_blacklist,
                starting_vars=self.starting_vars,
                builtin_whitelist=self.builtin_whitelist,
                names_for_user_list=self.names_for_user_list,
                helper_modules=self.helper_modules,
            )

        return self._start_server(initialization_timeout, build_start_message)

    def __repr__(self) -> str:
        return f"WorkspaceFixture(workspace_dir={self.workspace_dir})"
