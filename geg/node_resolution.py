import itertools

import networkx as nx

from ._geometry import distance


def node_resolution(G: nx.Graph) -> float:
    """Node resolution = min pairwise Euclidean distance / max.

    Paper §3.2 eq. (9). Computed over all unordered pairs of vertices in the
    layout; edge geometry is ignored. Returns 1.0 for single-node graphs, 0.0
    when all nodes are coincident.
    """
    if G.number_of_nodes() <= 1:
        return 1.0

    coords = [(d["x"], d["y"]) for _, d in G.nodes(data=True)]
    dists = [distance(a, b) for a, b in itertools.combinations(coords, 2)]
    if not dists:
        return 1.0
    d_max = max(dists)
    if d_max == 0:
        return 0.0
    return min(dists) / d_max
