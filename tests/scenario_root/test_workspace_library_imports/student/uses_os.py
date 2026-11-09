def import_os():
    import os

    return os.name


def import_os_path():
    import os.path

    return os.name


def dunder_import_os():
    return __import__("os").name
