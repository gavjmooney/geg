import math
from typing import Optional

import networkx as nx
import numpy as np
from scipy.spatial import cKDTree

from .geg_parser import get_convex_hull_area


def _connected_np(G: nx.Graph, k: Optional[int]) -> float:
    """Neighbourhood preservation on a connected component."""
    nodes = list(G.nodes())
    n = len(nodes)

    if n == 1:
        return 1.0

    if k is None:
        avg_deg = sum(dict(G.degree()).values()) / n
        k = math.floor(avg_deg)
    k = max(1, min(k, n - 1))

    A = nx.to_numpy_array(G, nodelist=nodes, dtype=bool)

    pts = np.array([(G.nodes[u]["x"], G.nodes[u]["y"]) for u in nodes])
    tree = cKDTree(pts)
    _, idxs = tree.query(pts, k=k + 1)  # includes self at idx 0

    K = np.zeros((n, n), dtype=bool)
    for i, neighbours in enumerate(idxs):
        for j in neighbours[1:]:  # skip self
            K[i, j] = True

    inter = np.logical_and(A, K).sum()
    union = np.logical_or(A, K).sum()
    return float(inter / union) if union > 0 else 1.0


def neighbourhood_preservation(G: nx.Graph, k: Optional[int] = None) -> float:
    """Neighbourhood preservation via Jaccard similarity in [0, 1].

    Compares topological adjacency A to the geometric k-nearest-neighbour
    matrix M^k: NP = |A ∧ M^k| / |A ∨ M^k|. Default k = floor(2|E|/|V|),
    i.e. floor(average degree).

    For disconnected drawings, per paper §3.3, returns a weighted sum of
    per-component NP scores, weights proportional to each component's
    convex-hull area. Singleton components (no pairs) contribute nothing.

    Args:
        G: NetworkX graph with node attributes 'x' and 'y'.
        k: Number of geometric neighbours to consider; defaults to
           floor(average degree) per-component.

    Returns:
        Float in [0, 1], 1 = perfect preservation.
    """
    if G.number_of_nodes() <= 1:
        return 1.0

    components = [G.subgraph(c).copy() for c in nx.connected_components(G.to_undirected())]
    if len(components) == 1:
        return _connected_np(G, k)

    scores = []
    weights = []
    for sub in components:
        if sub.number_of_nodes() <= 1:
            continue
        scores.append(_connected_np(sub, k))
        weights.append(get_convex_hull_area(sub))

    total = sum(weights)
    if total == 0:
        return 1.0
    return sum(s * w for s, w in zip(scores, weights)) / total
