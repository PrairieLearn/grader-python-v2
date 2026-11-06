CONSTANT = 5


def add_one(x):
    return x + 1


def raises_key_error():
    return {}["missing_key"]


def raises_import_error():
    raise ImportError("student import problem")


def imports_missing_module():
    import no_such_module_inside_function  # noqa: F401, PLC0415
