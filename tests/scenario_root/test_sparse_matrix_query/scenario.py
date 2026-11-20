"""End-to-end scenario: a scipy.sparse matrix produced by student code can be
queried back from the sandbox and checked, like the legacy CS357 sparse questions.
"""

import numpy as np
import pytest
import scipy.sparse as sp

from pytest_prairielearn_grader import ConfigObject
from pytest_prairielearn_grader.fixture import StudentFixture

# Importing scipy in the sandbox can take longer than the default 1 second timeout.
autograder_config = ConfigObject(sandbox_timeout=15)

DENSE = np.array([[1.0, 0.0, 2.0], [0.0, 3.0, 0.0], [4.0, 0.0, 5.0]])


@pytest.mark.grading_data(name="query csr matrix", points=1)
def test_query_csr_matrix(sandbox: StudentFixture) -> None:
    result = sandbox.query("modified_A", query_timeout=15)
    assert sp.issparse(result)
    assert result.format == "csr"
    np.testing.assert_array_equal(result.toarray(), DENSE)


@pytest.mark.grading_data(name="query csc matrix", points=1)
def test_query_csc_matrix(sandbox: StudentFixture) -> None:
    result = sandbox.query("col_matrix", query_timeout=15)
    assert result.format == "csc"
    np.testing.assert_array_equal(result.toarray(), DENSE)


@pytest.mark.grading_data(name="query coo matrix", points=1)
def test_query_coo_matrix(sandbox: StudentFixture) -> None:
    result = sandbox.query("coo_entries", query_timeout=15)
    assert result.format == "coo"
    np.testing.assert_array_equal(result.toarray(), DENSE)


@pytest.mark.grading_data(name="query index arrays", points=1)
def test_query_preserves_index_arrays(sandbox: StudentFixture) -> None:
    result = sandbox.query("modified_A", query_timeout=15)
    reference = sp.csr_matrix(DENSE)
    np.testing.assert_array_equal(result.indices, reference.indices)
    np.testing.assert_array_equal(result.indptr, reference.indptr)
    assert result.nnz == reference.nnz


@pytest.mark.grading_data(name="function returns sparse", points=1)
def test_function_returns_sparse(sandbox: StudentFixture) -> None:
    result = sandbox.query_function("scaled_matrix", 2.0, query_timeout=15)
    assert sp.issparse(result)
    np.testing.assert_array_equal(result.toarray(), DENSE * 2.0)
