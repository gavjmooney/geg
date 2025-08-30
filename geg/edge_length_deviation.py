from . import geg_parser
import networkx as nx
from svgpathtools import parse_path
from typing import Optional
import math

def get_average_edge_length(G: nx.Graph) -> float:
    """
    Compute the average drawn edge length.

    For each edge, if a 'path' attribute is present, its length is computed as
    the sum of segment lengths from the SVG path. Otherwise, the straight-line
    Euclidean distance between endpoints is used.

    Args:
        G: A NetworkX graph with node coordinates 'x', 'y' and optional edge 'path'.

    Returns:
        The mean edge length as a float (0.0 if there are no edges).
    """
    lengths = []
    for u, v, attrs in G.edges(data=True):
        if attrs.get('path'):
            # curved or polyline edge
            path = parse_path(attrs['path'])
            # sum each segments length to get the total
            L = sum(seg.length(error=1e-5) for seg in path)
            # print(L)
        else:
            # straight line fallback
            a = G.nodes[u]['x'], G.nodes[u]['y']
            b = G.nodes[v]['x'], G.nodes[v]['y']
            L = geg_parser.euclidean_distance(a, b)
            # print(u, v, L)
        lengths.append(L)

    if not lengths:
        return 0.0
    
    return sum(lengths) / len(lengths)


def edge_length_deviation(G: nx.Graph, ideal: Optional[float] = None) -> float:
    """
    Edge-length uniformity metric in [0, 1] based on relative deviation.

    For each edge, compute its length (using 'path' if present, else Euclidean).
    Measure the absolute relative deviation |L - ideal| / ideal, average over
    all edges, then map to [0, 1] using a reciprocal transformation 1/(1+d).

    Args:
        G: A NetworkX graph with node coordinates 'x', 'y' and optional edge 'path'.
        ideal: The target edge length. If None, uses the average drawn edge length.

    Returns:
        A float in [0, 1], where 1.0 indicates all edges match the ideal length.
    """
    m = G.number_of_edges()
    if m == 0:
        return 0.0

    if ideal is None:
        ideal = get_average_edge_length(G)

    total_rel_dev = 0.0
    for u, v, attrs in G.edges(data=True):
        if attrs.get('path'):
            path = parse_path(attrs['path'])
            L = sum(seg.length(error=1e-5) for seg in path)
        else:
            a = (G.nodes[u]['x'], G.nodes[u]['y'])
            b = (G.nodes[v]['x'], G.nodes[v]['y'])
            L = geg_parser.euclidean_distance(a, b)

        total_rel_dev += abs(L - ideal) / ideal

    avg_rel_dev = total_rel_dev / m

    # return math.exp(-avg_rel_dev) # Exponential decay into [0,1]

    return 1.0 / (1.0 + avg_rel_dev) # reciprocal
