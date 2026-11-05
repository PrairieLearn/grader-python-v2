import numpy as np

value = 42
array_value = np.array([1.0, 2.0])
large_value = list(range(200000))
tuple_value = (1, 2)
int_keys_value = {1: "one"}
shared = [1, 2, 3]
replaced_value = 1
forged_value = 2
unserializable = (i for i in range(3))


def read_shared():
    return shared


def add_twenty(x):
    return x + 20
