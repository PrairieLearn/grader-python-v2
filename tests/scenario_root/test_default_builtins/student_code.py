class Shape:
    def __init__(self, name):
        self.name = name

    @property
    def label(self):
        return f"{self.name}!"

    @staticmethod
    def sides():
        return 0

    @classmethod
    def make(cls, name):
        return cls(name)


class Square(Shape):
    def __init__(self):
        super().__init__("square")


def common_builtins(values):
    return [
        sum(values),
        any(v > 2 for v in values),
        all(v > 0 for v in values),
        list(reversed(values)),
        list(filter(lambda v: v % 2, values)),
        next(iter(values)),
        sorted(frozenset(values)),
        format(3.14159, ".2f"),
        bin(5),
        ascii("é"),
        type(values).__name__,
        isinstance(object(), object),
    ]


def classes():
    square = Square()
    return [square.label, Square.sides(), Shape.make("circle").name]


def call_open():
    return open("data.txt").read()
