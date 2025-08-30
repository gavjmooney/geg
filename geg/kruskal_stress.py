from . import geg_parser
import numpy as np
import networkx as nx
from sklearn.metrics import pairwise_distances
from sklearn.isotonic import IsotonicRegression
from typing import List

def kruskal_stress(G: nx.Graph) -> float:
    """
    Kruskal stress quality metric for a 2D layout, mapped to [0, 1].

    Computes all-pairs shortest path distances in the graph (d_ij) and 2D
    Euclidean distances in the layout (x_ij). Fits an isotonic regression
    h(d_ij) to the sorted pairs and computes stress = sqrt(sum((x_ij-h_ij)^2)
    / sum(x_ij^2)). Returns 1 - stress so that higher is better.

    Args:
        G: A NetworkX graph with node coordinates 'x' and 'y'.

    Returns:
        A float in [0, 1], where 1 indicates perfect monotone correspondence
        between graph-theoretic and layout distances.
    """

    if G.number_of_nodes() == 1:
        return 1.0

    # All-pairs shortest path lengths
    apsp = dict(nx.all_pairs_shortest_path_length(G))

    # Node ordering and layout matrix X
    nodes = list(G.nodes())
    X = np.array([[G.nodes[n]['x'], G.nodes[n]['y']] for n in nodes])

    # Distance matrices: embedding vs. graph
    Xij = pairwise_distances(X)
    D   = np.array([[apsp[i][j] for i in nodes] for j in nodes])

    # Extract upper triangles (k=1 to skip diagonal)
    triu = np.triu_indices_from(Xij, k=1)
    xij, dij = Xij[triu], D[triu]

    # Sort by graph distances
    order = np.argsort(dij)
    dij_sorted = dij[order]
    xij_sorted = xij[order]

    # Fit isotonic regression to get fitted distances hij
    hij = IsotonicRegression().fit(dij_sorted, xij_sorted).predict(dij_sorted)

    # Compute Kruskal stress and map to [0, 1]
    raw = np.sum((xij_sorted - hij)**2)
    norm = np.sum(xij_sorted**2)
    if norm == 0:
        return 1.0
    kruskal = np.sqrt(raw / norm)
    return 1.0 - kruskal
