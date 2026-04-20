from typing import Any, List, Optional, Tuple

import networkx as nx

from .edge_crossings import edge_crossings


def crossing_angle(
    G: nx.Graph,
    ideal_angle: float = 90.0,
    crossings: Optional[List[Tuple[Any, float]]] = None,
) -> float:
    """Crossing-angle quality score in [0, 1].

    Paper §3.2 eq. (2):
        CA(D) = 1 - (1/|X|) * sum_x (φ - φ^min_x) / φ
    where φ = 90° and φ^min_x is the acute angle between the two crossing
    edges at x. X is the set of crossings in the drawing. Returns 1.0 if there
    are no crossings.

    Args:
        G: NetworkX graph with edge 'path' attrs.
        ideal_angle: Target crossing angle in degrees (default 90, per paper).
        crossings: Optional pre-computed list of (position, angle_deg) tuples.
            If None, computed via `edge_crossings(G, return_crossings=True)`.

    Returns:
        Float in [0, 1], 1 = every crossing is at the ideal angle (or no crossings).
    """
    if crossings is None:
        _, crossings = edge_crossings(G, return_crossings=True)

    if not crossings:
        return 1.0

    shortfall_sum = sum(
        (ideal_angle - angle) / ideal_angle for _, angle in crossings
    )
    return 1.0 - shortfall_sum / len(crossings)
