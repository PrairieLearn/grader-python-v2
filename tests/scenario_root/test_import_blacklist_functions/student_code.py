import numpy as np
import numpy.linalg as la


def numpy_attribute():
    return np.linalg.inv([[2.0]]).tolist()


def module_alias():
    return la.inv([[2.0]]).tolist()


def from_import():
    from numpy.linalg import inv

    return inv([[2.0]]).tolist()


def other_function():
    return la.solve([[2.0]], [1.0]).tolist()
