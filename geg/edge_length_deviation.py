from typing import Optional

import networkx as nx

from ._geometry import distance
from ._paths import parse_path


def _edge_length(G: nx.Graph, u, v, attrs: dict) -> float:
    """Drawn length of an edge.

    Uses the SVG 'path' arc length when present (via svgpathtools' numerical
    integration), otherwise the straight-line Euclidean distance between the
    endpoint node coordinates.
    """
    path_str = attrs.get("path")
    if path_str:
        path = parse_path(path_str)
        return float(sum(seg.length(error=1e-5) for seg in path))
    a = (G.nodes[u]["x"], G.nodes[u]["y"])
    b = (G.nodes[v]["x"], G.nodes[v]["y"])
    return distance(a, b)


def get_average_edge_length(G: nx.Graph) -> float:
    """Mean drawn edge length (0.0 for edgeless graphs)."""
    lengths = [_edge_length(G, u, v, attrs) for u, v, attrs in G.edges(data=True)]
    if not lengths:
        return 0.0
    return sum(lengths) / len(lengths)


def edge_length_deviation(G: nx.Graph, ideal: Optional[float] = None) -> float:
    """Edge-length deviation metric in [0, 1].

    Paper §3.2 eq. (4):
        ELD(D) = 1 / (1 + (1/|E|) * sum_e |L(e) - L_ideal| / L_ideal)
    with L_ideal the average drawn edge length (or a user-supplied value).

    Edge lengths use the SVG path arc length when present, otherwise the
    straight-line Euclidean endpoint distance.

    Degenerate cases:
        - No edges: returns 1.0 (vacuously uniform).
        - All edges length 0 (so L_ideal = 0): returns 1.0 — the paper's
          "ELD = 1 iff all edges have the same length" extends to the
          equal-but-zero case.

    Args:
        G: NetworkX graph with node 'x'/'y' and optional edge 'path' attrs.
        ideal: Target edge length. Defaults to the average drawn length.

    Returns:
        Float in [0, 1], 1 = all edges the same length.
    """
    m = G.number_of_edges()
    if m == 0:
        return 1.0

    lengths = [_edge_length(G, u, v, attrs) for u, v, attrs in G.edges(data=True)]

    if ideal is None:
        ideal = sum(lengths) / m

    if ideal == 0:
        # All lengths are zero (or an explicit ideal=0 was passed); the
        # "same length" condition holds vacuously.
        return 1.0

    avg_rel_dev = sum(abs(L - ideal) for L in lengths) / (m * ideal)
    return 1.0 / (1.0 + avg_rel_dev)
