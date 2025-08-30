
from . import geg_parser as geg
import networkx as nx
from .edge_crossings import edge_crossings
import math
from typing import Optional, List, Tuple, Any

def crossing_angle(G: nx.Graph, ideal_angle: float = 90, crossings: Optional[List[Tuple[Any, float]]] = None) -> float:
    """
    Compute a crossing-angle quality score relative to an ideal angle.

    If crossings are not provided, they are computed. For each edge crossing,
    the crossing angle (in degrees) is compared to the ideal (default 90).
    The metric aggregates the normalized shortfall (ideal - angle)/ideal across
    all crossings and returns 1 minus the average shortfall.

    Notes:
        - If there are no crossings, returns 1.0.
        - Crossing angles are assumed to be the acute angles in [0, 90].

    Args:
        G: A NetworkX graph with edge paths.
        ideal_angle: The desired crossing angle in degrees (default 90).
        crossings: Optional list of crossings as tuples where the second element
            is the crossing angle in degrees. If None, crossings are computed.

    Returns:
        A float in [0, 1], with higher values indicating better crossing angles.
    """

    # No crossings passed to function
    if not crossings:
        _, crossings = edge_crossings(G, return_crossings=True)

    # No crossings in drawing
    if not crossings:
        return 1.0
        

    angles = [x[1] for x in crossings]

    min_angles_score_sum = 0
   
    for angle in angles:
        # accumulate normalised deviation from the ideal
        min_angles_score_sum += (ideal_angle - angle) / ideal_angle

    return 1 - (min_angles_score_sum / len(angles))
