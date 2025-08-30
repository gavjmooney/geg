from . import geg_parser
import math
import networkx as nx
from typing import Hashable, List
from svgpathtools import parse_path, Path, Line, CubicBezier, QuadraticBezier, Arc

def reverse_svg_path(path_str: str) -> str:
    """
    Reverse the direction of an SVG path string while preserving geometry.

    Args:
        path_str: The SVG path 'd' attribute representing a single path.

    Returns:
        A new SVG path string with reversed direction. Line, cubic, quadratic,
        and arc segments are handled so that the resulting geometry is unchanged
        except for traversal direction.
    """
    # Parse into a Path (a sequence of segments)
    path = parse_path(path_str)
    
    reversed_segments = []
    # Walk the segments in reverse order, and flip each one:
    for seg in reversed(path):
        if isinstance(seg, Line):
            # swap start/end
            reversed_segments.append(Line(seg.end, seg.start))
        elif isinstance(seg, CubicBezier):
            # swap start/end and swap control1<->control2
            reversed_segments.append(CubicBezier(
                seg.end,
                seg.control2,
                seg.control1,
                seg.start
            ))
        elif isinstance(seg, QuadraticBezier):
            # swap start/end, control remains the same
            reversed_segments.append(QuadraticBezier(
                seg.end,
                seg.control,
                seg.start
            ))
        elif isinstance(seg, Arc):
            # swap start/end, keep radii/rotation, flip sweep-flag
            reversed_segments.append(Arc(
                seg.end,
                seg.radius,
                seg.rotation,
                seg.large_arc,
                not seg.sweep,
                seg.start
            ))
        else:
            # any other segment type with a .reversed() helper
            reversed_segments.append(seg.reversed())
    
    # Rebuild into a new Path and return its SVG 'd' string
    reversed_path = Path(*reversed_segments)
    return reversed_path.d()

def orient_svg_path_for_node(path_str: str, node_x: float, node_y: float, tol: float = 1e-6) -> str:
    """
    Ensure an edge path is oriented to start at the given node position.

    Many layout metrics depend on a consistent local orientation of each edge
    around a node. This function checks whether the first segment of the path
    begins at (node_x, node_y). If not (within a tolerance), the path is
    reversed so that it does.

    Args:
        path_str: The SVG path 'd' attribute for the edge.
        node_x: X coordinate of the node.
        node_y: Y coordinate of the node.
        tol: Absolute tolerance for matching the start point to the node.

    Returns:
        The original path if already oriented from the node; otherwise, a
        reversed path string.
    """
    path = parse_path(path_str)
    if not path:
        return path_str

    start = path[0].start
    if abs(start.real - node_x) < tol and abs(start.imag - node_y) < tol:
        return path_str
    else:
        return reverse_svg_path(path_str)

def get_outbound_edges(G: nx.Graph, node: Hashable) -> List:
    """
    Return the set of edges incident to a node (or outgoing if directed).

    The return tuple shape matches NetworkX conventions and depends on whether
    the input graph is a multigraph:
    - Simple Graph/DiGraph: (u, v, data)
    - MultiGraph/MultiDiGraph: (u, v, key, data)

    Args:
        G: A NetworkX graph containing edge attribute 'path' per drawing.
        node: The node identifier to query.

    Returns:
        A list of incident (or outgoing) edges with their attributes.
    """
    if G.is_multigraph():
        kw = dict(keys=True, data=True)
    else:
        kw = dict(data=True)

    if G.is_directed():
        return list(G.out_edges(node, **kw))
    else:
        return list(G.edges(node, **kw))

def angular_resolution_min_angle(G: nx.Graph) -> float:
    """
    Angular-resolution score based on the minimum angular gap at each node.

    For each non-bend node with degree >= 2, compute the angles of all incident
    edges around the node using the unit tangent of each path's first segment
    (oriented to start at the node). The smallest gap between successive angles
    (including wrap-around) is compared to the ideal gap 360/deg(node). The
    per-node normalized shortfall (ideal - min_gap)/ideal is averaged across
    nodes and inverted to map into [0, 1] (1 is best).

    Notes:
        - Nodes with degree <= 1 are ignored.
        - Nodes with attribute is_segment=True (promoted bend points) are ignored.
        - Uses SVG coordinates. The y-axis is flipped to Cartesian for angles.

    Args:
        G: A NetworkX graph whose edges have a 'path' attribute ('M ... L ...').

    Returns:
        A float in [0, 1] indicating angular resolution quality (higher is better).
    """

    min_angles_score_sum = 0
    nodes_count = 0

    for node in G:
        # Ignore degree 1 nodes
        if G.degree[node] <= 1:
            continue
        
        # Ignore bend nodes
        if G.nodes[node].get("is_segment", False):
            continue

        nodes_count += 1
        ideal = 360 / G.degree[node]
        actual_min = 360

        x, y = G.nodes[node]['x'], G.nodes[node]['y']
        raw_paths = []
        
        for u, v, *rest in get_outbound_edges(G, node):
            data = rest[-1]
            raw = data['path']
            raw_paths.append(raw)

            # self loop should be counted as two edges
            if u == v:
                raw_paths.append(reverse_svg_path(raw))

        angles = []
        for raw in raw_paths:
            path_str = orient_svg_path_for_node(raw, x, y)

            path = parse_path(path_str)
            seg0 = path[0]  # first segment of the path

            # compute unit tangent at the start of the segment
            if seg0.start == seg0.end:
                # print(f"Warning: degenerate segment found in path '{path_str}' for node {node}")
                continue

            tangent = seg0.unit_tangent(0.0) 
   
            vx, vy = tangent.real, -tangent.imag # flip y axis to convert svg coord to cartesian.

            raw = math.atan2(vy, vx) # angle from +x axis
            theta = math.degrees(raw - math.pi/2) % 360 # angle from y axis
            theta_cw = (360 - theta) % 360 # make angles clockwise from y axis
            angles.append(theta_cw)

        # need at least two edges to have an angular separation
        if len(angles) < 2:
            continue
        
        angles.sort()
        # compute gaps between successive angles, including wrap-around
        gaps = [angles[i+1] - angles[i] for i in range(len(angles)-1)]
        gaps.append((angles[0] + 360.0) - angles[-1])
        actual_min = min(gaps)


        # accumulate normalised deviation from the ideal
        min_angles_score_sum += (ideal - actual_min) / ideal

    if nodes_count == 0:
        return 1.0

    return 1 - (min_angles_score_sum / nodes_count)


def angular_resolution_avg_angle(G: nx.Graph) -> float:
    """
    Angular-resolution score using the average deviation of gaps from ideal.

    For each eligible node (degree >= 2 and not a bend node), compute the set
    of angular gaps between successive incident edges (with wrap-around). The
    ideal gap is 360/deg(node). Because the mean gap always equals the ideal,
    we score uniformity using the mean absolute deviation of the gaps from the
    ideal, normalized by the ideal, then average across nodes and invert to map
    into [0, 1] (1 is best).

    This treatment is symmetric: gaps greater or smaller than the ideal both
    contribute proportionally via absolute deviation.

    Args:
        G: A NetworkX graph whose edges have a 'path' attribute ('M ... L ...').

    Returns:
        A float in [0, 1] indicating angular uniformity quality (higher is better).
    """

    avg_deviation_score_sum = 0
    nodes_count = 0

    for node in G:
        # Ignore degree 1 nodes
        if G.degree[node] <= 1:
            continue
        
        # Ignore bend nodes
        if G.nodes[node].get("is_segment", False):
            continue

        nodes_count += 1
        ideal = 360 / G.degree[node]

        x, y = G.nodes[node]['x'], G.nodes[node]['y']
        raw_paths = []
        
        for u, v, *rest in get_outbound_edges(G, node):
            data = rest[-1]
            raw = data['path']
            raw_paths.append(raw)

            # self loop should be counted as two edges
            if u == v:
                raw_paths.append(reverse_svg_path(raw))

        angles = []
        for raw in raw_paths:
            path_str = orient_svg_path_for_node(raw, x, y)

            path = parse_path(path_str)
            seg0 = path[0]  # first segment of the path

            # compute unit tangent at the start of the segment
            if seg0.start == seg0.end:
                # print(f"Warning: degenerate segment found in path '{path_str}' for node {node}")
                continue

            tangent = seg0.unit_tangent(0.0) 
   
            vx, vy = tangent.real, -tangent.imag # flip y axis to convert svg coord to cartesian.

            raw = math.atan2(vy, vx) # angle from +x axis
            theta = math.degrees(raw - math.pi/2) % 360 # angle from y axis
            theta_cw = (360 - theta) % 360 # make angles clockwise from y axis
            angles.append(theta_cw)

        # need at least two edges to have an angular separation
        if len(angles) < 2:
            continue
        
        angles.sort()
        # compute gaps between successive angles, including wrap-around
        gaps = [angles[i+1] - angles[i] for i in range(len(angles)-1)]
        gaps.append((angles[0] + 360.0) - angles[-1])

        # Average gap equals ideal by construction (sum of gaps = 360).
        # Use mean absolute deviation from ideal to capture uniformity.
        mean_abs_dev = sum(abs(g - ideal) for g in gaps) / len(gaps)

        # accumulate normalised deviation from the ideal
        avg_deviation_score_sum += (mean_abs_dev / ideal)

    if nodes_count == 0:
        return 1.0

    return 1 - (avg_deviation_score_sum / nodes_count)
