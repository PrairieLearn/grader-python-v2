import numpy as np


def edge_total():
    return float(np.loadtxt("edges.txt").sum())
