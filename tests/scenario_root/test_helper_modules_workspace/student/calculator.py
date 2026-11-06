import helper_function
import second_helper


def triple_it(x):
    return helper_function.triple(x)


def source():
    return helper_function.SOURCE


def add_one(x):
    return second_helper.add_one(x)


def total(values):
    return helper_function.total(values)


def own_sum(values):
    return sum(values)


def import_ans():
    import ans

    return ans.ANSWER


def import_json():
    import json

    return json
