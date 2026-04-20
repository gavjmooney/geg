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


def edge_length_deviation(
    G: nx.Graph,
    ideal: Optional[float] = None,
    *,
    weight: Optional[str] = None,
) -> float:
    """Edge-length deviation metric in [0, 1].

    Paper §3.2 eq. (4):
        ELD(D) = 1 / (1 + (1/|E|) * sum_e |L(e) - L_ideal| / L_ideal)
    with L_ideal the average drawn edge length (or a user-supplied value).

    Edge lengths use the SVG path arc length when present, otherwise the
    straight-line Euclidean endpoint distance.

    Weighted variant (opt-in via `weight`): every edge aims for its own
    ideal length L*(e) proportional to its weight. The proportionality
    constant `s = sum(L) / sum(|w|)` makes the total ideal length equal
    the total drawn length (so the ratios compare on a common footing and
    doubling every drawn length leaves the score unchanged). Per-edge
    relative deviation then becomes `|L(e) - L*(e)| / L*(e)`. Negative
    weights are treated as their magnitude (the spring-rest-length
    interpretation has no sign), and zero weights raise `ValueError`.
    With all weights equal, `L*(e) = L_ideal` for every e and the formula
    is identical to the unweighted one.

    Degenerate cases:
        - No edges: returns 1.0 (vacuously uniform).
        - All edges length 0 (unweighted): returns 1.0 — the paper's "ELD
          = 1 iff all edges have the same length" extends to equal-but-
          zero. In the weighted variant, a sum-of-lengths of 0 (everything
          coincident) also returns 1.0.

    Args:
        G: NetworkX graph with node 'x'/'y' and optional edge 'path' attrs.
        ideal: Target edge length (unweighted variant only). Defaults to
            the average drawn length.
        weight: Edge attribute name whose value gives the *desired relative
            length* of each edge. Default `None` = unweighted. Incompatible
            with `ideal`; passing both raises `ValueError`.

    Returns:
        Float in [0, 1], 1 = every edge is exactly its ideal length (or
        every drawn length matches every other).
    """
    m = G.number_of_edges()
    if m == 0:
        return 1.0

    lengths = [_edge_length(G, u, v, attrs) for u, v, attrs in G.edges(data=True)]

    if weight is not None:
        if ideal is not None:
            raise ValueError("`ideal` and `weight` are mutually exclusive")
        weights = []
        for u, v, attrs in G.edges(data=True):
            raw = attrs.get(weight)
            if raw is None:
                raise ValueError(
                    f"edge ({u!r}, {v!r}) has no {weight!r} attribute"
                )
            w = abs(float(raw))
            if w == 0:
                raise ValueError(
                    f"edge ({u!r}, {v!r}) has zero {weight!r}; weighted ELD "
                    "requires non-zero edge weights"
                )
            weights.append(w)
        total_length = sum(lengths)
        total_weight = sum(weights)
        if total_length == 0:
            return 1.0
        # Global scale `s`: makes total ideal length match total drawn length.
        s = total_length / total_weight
        avg_rel_dev = sum(
            abs(L - w * s) / (w * s) for L, w in zip(lengths, weights)
        ) / m
        return 1.0 / (1.0 + avg_rel_dev)

    if ideal is None:
        ideal = sum(lengths) / m

    if ideal == 0:
        # All lengths are zero (or an explicit ideal=0 was passed); the
        # "same length" condition holds vacuously.
        return 1.0

    avg_rel_dev = sum(abs(L - ideal) for L in lengths) / (m * ideal)
    return 1.0 / (1.0 + avg_rel_dev)
