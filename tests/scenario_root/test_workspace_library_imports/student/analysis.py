import statistics

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

NORM = float(np.linalg.norm([3, 4]))
MEAN = statistics.mean([1, 2, 3])
LINES = len(plt.plot([1, 2]))
