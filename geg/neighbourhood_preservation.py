from . import geg_parser
import networkx as nx
import math
import numpy as np
from scipy.spatial import cKDTree
from typing import Optional

def neighbourhood_preservation(G: nx.Graph, k: Optional[int] = None) -> float:
    """
    Neighbourhood preservation score via Jaccard similarity in [0, 1].

    Compares topological adjacency to geometric k-nearest neighbours. Builds a
    boolean adjacency matrix A from the graph and a boolean matrix K where
    K[i, j] is True if j is among the k closest nodes to i in the layout.
    Returns J(A, K) = |A <intersection> K| / |A <union> K|.

    Args:
        G: A NetworkX graph with node coordinates 'x' and 'y'.
        k: Number of geometric neighbours to consider; if None, uses
           floor(average degree).

    Returns:
        A float in [0, 1], where higher means better preservation of
        neighbourhoods.
    """

    nodes = list(G.nodes())
    n = len(nodes)

    if n == 1:
        return 1.0

    # Default k = floor(avg degree)
    if k is None:
        avg_deg = sum(dict(G.degree()).values())/n
        k = math.floor(avg_deg)

    # Ensure k is at most n-1
    k = max(1, min(k, n-1))

    # Adjaceny matrix
    A = nx.to_numpy_array(G, nodelist=nodes, dtype=bool)

    # build KD‐tree 
    pts = np.array([ (G.nodes[u]['x'], G.nodes[u]['y']) for u in nodes ])
    tree = cKDTree(pts)
    dists, idxs = tree.query(pts, k=k+1)  # includes self at idx 0

    # K matrix (1 if j is in k nearest geometric neighbours of i)
    K = np.zeros((n,n), dtype=bool)
    for i, neighbours in enumerate(idxs):
        for j in neighbours[1:]:       # skip the first one (itself)
            K[i,j] = True

    # Compute Jaccard similarity on boolean matrices
    inter = np.logical_and(A, K).sum()
    union = np.logical_or (A, K).sum()
    return float(inter/union) if union > 0 else 1.0
