import numpy as np
import pandas as pd

TOTAL = int(pd.DataFrame({"a": np.array([1, 2, 3])})["a"].sum())


def import_statistics():
    import statistics

    return statistics.mean([1, 2])
