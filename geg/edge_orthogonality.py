import math
from . import geg_parser
import networkx as nx
from svgpathtools import parse_path
from typing import Optional

def edge_orthogonality(G: nx.Graph) -> float:
        """
        Orthogonality score for straight-line edges in [0, 1].

        For each straight edge, compute its angle relative to the horizontal,
        convert to the nearest orthogonal deviation (0 for axis-aligned, 1 for
        a 45-degree diagonal), then average across edges and invert as 1 - mean.

        Args:
            G: A NetworkX graph with node coordinates 'x' and 'y'.

        Returns:
            A float in [0, 1] where 1.0 means perfectly orthogonal (all edges
            aligned to horizontal/vertical) and 0 means highly non-orthogonal.
        """
        if G.number_of_edges() == 0:
            return 0.0
        
        ortho_list = []

        # Iterate over each edge and compute its minimum deviation from orthogonal axes
        for e in G.edges:
            source = e[0]
            target = e[1]

            x1, y1 = G.nodes[source]["x"], G.nodes[source]["y"]
            x2, y2 = G.nodes[target]["x"], G.nodes[target]["y"]

            if x2 - x1 == 0:
                gradient = 0
                # note: gradient of 0 is incorrect for a vertical line, but since we only care about deviation from
                # orthogonal axes, it's fine in this case
            else:
                gradient = (y2 - y1) / (x2 - x1) 

            angle = math.degrees(math.atan(abs(gradient)))

            edge_ortho = min(angle, abs(90-angle), 180-angle) / 45.0
            ortho_list.append(edge_ortho)

        # Return 1 minus the average deviation
        return 1 - (sum(ortho_list) / G.number_of_edges())



def curved_edge_orthogonality(G: nx.Graph, global_segments_N: int = 10) -> float:
    """
    Orthogonality score for curved/polyline edges via length-weighted segments.

    Each curved edge is approximated by many straight segments (via
    geg.approximate_edge_polyline). For each segment we compute deviation from
    the nearest orthogonal direction, then weight by the segment length over the
    edge's total length. We average over edges and invert so 1=perfectly
    orthogonal.

    Args:
        G: A NetworkX graph with edge 'path' attributes.
        global_segments_N: Sampling density for curve approximation.

    Returns:
        A float in [0, 1] where 1 indicates perfect orthogonality.
    """

    ortho_list = []

    for u, v, attrs in G.edges(data=True):
        # approximate the full path as a sequence of points
        poly = geg_parser.approximate_edge_polyline(G, (u, v, attrs), global_segments_N)
        if len(poly) < 2:
            # no real segment: treat as perfectly orthogonal
            ortho_list.append(0.0)
            continue

        # total length of this edge
        total_len = sum(
            geg_parser.euclidean_distance(poly[i], poly[i+1])
            for i in range(len(poly)-1)
        )
        if total_len == 0:
            ortho_list.append(0.0)
            continue

        # accumulate weighted deviation for each segment
        edge_dev = 0.0
        for p0, p1 in zip(poly[:-1], poly[1:]):
            seg_len = geg_parser.euclidean_distance(p0, p1)
            dx = p1[0] - p0[0]
            dy = p1[1] - p0[1]

            # angle between this segment and the horizontal axis
            if dx == 0:
                angle = 90.0
            else:
                angle = math.degrees(math.atan(abs(dy / dx)))

            # deviation from the nearest orthogonal direction, scaled so 0 = perfect, 1 = 45 degrees diagonal
            seg_ortho = min(angle, abs(90 - angle), 180 - angle) / 45.0

            # weight by segment's proportion of the edge’s total length
            edge_dev += seg_ortho * (seg_len / total_len)

        ortho_list.append(edge_dev)


    if not ortho_list:
        return 1.0

    # average deviation across all edges, then invert so 1=perfect orthogonality
    avg_dev = sum(ortho_list) / len(ortho_list)
    return 1 - avg_dev
