def import_os():
    import os

    return os.name


def import_os_path():
    import os.path

    return os.getcwd()


def from_os_import_path():
    from os import path

    return path.sep


def import_json():
    import json

    return json.dumps(1)
