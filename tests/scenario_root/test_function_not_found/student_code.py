not_callable = 5


def add_one(x):
    return x + 1


def raises_key_error():
    print("before the error")
    return {}["missing_key"]


def raises_key_error_with_function_name():
    raise KeyError("missing_function")


def raises_attribute_error():
    return add_one.missing_attribute


def raises_import_error():
    raise ImportError("student import problem")


def raises_name_error():
    return undefined_variable  # noqa: F821
