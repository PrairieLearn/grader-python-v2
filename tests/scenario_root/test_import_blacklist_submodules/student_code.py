def import_matplotlib():
    import matplotlib

    return matplotlib.__name__


def import_pyplot():
    import matplotlib.pyplot

    return matplotlib.pyplot.__name__


def from_matplotlib_import_pyplot():
    from matplotlib import pyplot

    return pyplot.__name__


def from_matplotlib_import_colors():
    from matplotlib import colors

    return colors.__name__
