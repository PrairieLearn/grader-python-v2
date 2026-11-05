class Thing:
    pass


def returns_thing(x):
    print("called returns_thing")
    return Thing()


def returns_nested_thing(x):
    return [x, {"thing": Thing()}]


def returns_self_reference(x):
    items = [x]
    items.append(items)
    return items


def add_one(x):
    return x + 1
