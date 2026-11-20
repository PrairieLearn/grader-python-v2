import numpy as np
import scipy.sparse as sp

dense = np.array([[1.0, 0.0, 2.0], [0.0, 3.0, 0.0], [4.0, 0.0, 5.0]])

modified_A = sp.csr_matrix(dense)
col_matrix = sp.csc_matrix(dense)
coo_entries = sp.coo_matrix(dense)


def scaled_matrix(factor):
    return (modified_A * factor).tocsr()
