import helper_function
import helper_function as alias
from helper_function import triple

from_student = helper_function.triple(4)
from_alias = alias.SCALE * 5


def uses_helper(x):
    return triple(x)


def import_when_called(x):
    import helper_function as late

    return late.triple(x)


def same_module():
    import helper_function as late

    return late is hf and late is alias


def through_second_helper(x):
    import second_helper

    return second_helper.triple_plus_one(x)


def import_ans():
    import ans

    return ans.ANSWER


def import_setup_code():
    import setup_code

    return setup_code


def import_scenario():
    import test_helper_modules

    return test_helper_modules


def helper_imports_ans():
    import second_helper

    return second_helper.import_ans()
