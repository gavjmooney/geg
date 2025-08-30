from . import geg_parser
import itertools
import math
import networkx as nx

def node_resolution(G: nx.Graph) -> float:
    """
    Node resolution score as min-to-max pairwise distance ratio in [0, 1].

    For layouts with at least two nodes, computes all pairwise Euclidean
    distances between nodes and returns min(d)/max(d). A single-node graph
    returns 1.0. If all nodes overlap (max distance == 0), returns 0.0.

    Args:
        G: A NetworkX graph with node coordinates 'x' and 'y'.

    Returns:
        A float in [0, 1] indicating relative node separation.
    """
    if G.number_of_nodes() == 1:
        return 1.0
    
    coords = [(d['x'], d['y']) for _, d in G.nodes(data=True)]
    dists = [math.hypot(x1 - x2, y1 - y2) for (x1, y1), (x2, y2) in itertools.combinations(coords, 2)]

    if not dists:
        return 1.0
    d_max = max(dists)
    if d_max == 0:
        return 0.0
    return min(dists) / d_max
