import pytest_prairielearn_grader.server_data
from pytest_prairielearn_grader import server_data
from pytest_prairielearn_grader.server_data import from_server_json
from pytest_prairielearn_grader.server_data import params

x = params["seed"] + server_data.params["seed"] + pytest_prairielearn_grader.server_data.params["seed"]
A = from_server_json(params["A"])
