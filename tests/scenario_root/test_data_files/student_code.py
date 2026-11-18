edge_total = float(edges.sum())
weights = np.loadtxt("data/weights.txt").tolist()

# Student code must not be able to change the copies it reads.
try:
    np.savetxt("edges.txt", np.zeros(2))
    overwrite_error = None
except OSError as e:
    overwrite_error = e.__class__.__name__

try:
    np.savetxt("new_file.txt", np.zeros(2))
    create_error = None
except OSError as e:
    create_error = e.__class__.__name__
