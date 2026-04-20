from typing import Any, Dict, Optional

import networkx as nx
import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import pairwise_distances

from .geg_parser import get_convex_hull_area


def _connected_kruskal(G: nx.Graph, *, apsp: Optional[Dict[Any, Dict[Any, int]]] = None) -> float:
    """Kruskal stress on a connected component, mapped to [0, 1].

    `apsp` — if given, a precomputed all-pairs-shortest-path-length dict
    covering at least the nodes of `G` (extra entries are ignored). When
    omitted, APSP is computed fresh on `G`.
    """
    nodes = list(G.nodes())
    if apsp is None:
        apsp = dict(nx.all_pairs_shortest_path_length(G))

    X = np.array([[G.nodes[n]["x"], G.nodes[n]["y"]] for n in nodes])

    Xij = pairwise_distances(X)
    D = np.array([[apsp[i][j] for i in nodes] for j in nodes])

    triu = np.triu_indices_from(Xij, k=1)
    xij, dij = Xij[triu], D[triu]

    order = np.argsort(dij)
    dij_sorted = dij[order]
    xij_sorted = xij[order]

    hij = IsotonicRegression().fit(dij_sorted, xij_sorted).predict(dij_sorted)

    raw = np.sum((xij_sorted - hij) ** 2)
    norm = np.sum(xij_sorted ** 2)
    if norm == 0:
        return 1.0
    return 1.0 - float(np.sqrt(raw / norm))


def kruskal_stress(
    G: nx.Graph,
    *,
    apsp: Optional[Dict[Any, Dict[Any, int]]] = None,
) -> float:
    """Kruskal stress metric mapped to [0, 1] (higher is better).

    Fits an isotonic regression h(d_ij) to pairs of (graph-theoretic distance,
    layout Euclidean distance) and reports 1 - sqrt(sum((x_ij-h_ij)^2)/sum(x_ij^2)).

    For disconnected drawings, per paper §3.3, returns a weighted sum of the
    per-component scores, weights proportional to each component's convex-hull
    area. Singleton components contribute nothing (no pairs).

    Args:
        G: NetworkX graph with node attributes 'x' and 'y'.
        apsp: Optional precomputed all-pairs-shortest-path-length dict on
            the undirected view of `G`. Useful in batch contexts where the
            same APSP feeds graph-property metrics (diameter, radius,
            avg_shortest_path_length). When omitted, APSP is computed fresh
            per connected component.

    Returns:
        Float in [0, 1], 1 = perfect monotone correspondence.
    """
    if G.number_of_nodes() <= 1:
        return 1.0

    # Kruskal stress compares Euclidean distance (symmetric) to graph-theoretic
    # distance. On a DiGraph, shortest-path reachability becomes asymmetric
    # and sinks can't reach anyone, which breaks the pairwise distance matrix.
    # Treat the graph as undirected for the metric computation.
    if G.is_directed():
        G = G.to_undirected(as_view=True)

    components = [G.subgraph(c).copy() for c in nx.connected_components(G)]
    if len(components) == 1:
        return _connected_kruskal(G, apsp=apsp)

    scores = []
    weights = []
    for sub in components:
        if sub.number_of_nodes() <= 1:
            continue
        scores.append(_connected_kruskal(sub, apsp=apsp))
        weights.append(get_convex_hull_area(sub))

    total = sum(weights)
    if total == 0:
        # Every non-singleton component is itself degenerate (collinear with
        # zero extent). Treat as nothing to penalise.
        return 1.0
    return sum(s * w for s, w in zip(scores, weights)) / total
