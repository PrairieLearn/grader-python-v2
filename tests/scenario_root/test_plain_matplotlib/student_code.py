import matplotlib.pyplot as plt
import numpy as np

x = np.arange(0, 11)
fx = np.exp(x)
plt.semilogy(x, fx, label="exp")
plt.xlabel("x")
plt.ylabel("f(x)")
plt.title("Growth")
plt.legend()
plot = plt.gca()
figure = plt.gcf()


def make_axes():
    _, axes = plt.subplots()
    axes.plot([1, 2, 3], [2, 4, 6], label="doubled")
    axes.set_xlabel("Input")
    axes.set_ylabel("Output")
    axes.set_title("Doubling")
    axes.legend()
    return axes


def make_subplots():
    figure, (left, right) = plt.subplots(1, 2)
    left.scatter([1, 2], [3, 4])
    right.bar(["a", "b"], np.array([5, 6]))
    return figure


def make_errorbar():
    _, axes = plt.subplots()
    axes.errorbar([1, 2], [3, 4], yerr=[0.1, 0.2])
    return axes


errorbar_plot = make_errorbar()
