value = 42
shared = [1, 2, 3]
unserializable = (i for i in range(3))


def read_shared():
    return shared


def add_twenty(x):
    return x + 20
