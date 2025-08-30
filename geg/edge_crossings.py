import networkx as nx
from svgpathtools import parse_path, Line, Path
from . import geg_parser
# import geg
import math
import itertools
from typing import Iterable, List, Optional, Sequence, Tuple, Union

import xml.etree.ElementTree as ET

def annotate_svg(input_svg_path: str, output_svg_path: str, points: Iterable[Tuple[float, float]], radius: float = 5, color: str = 'red') -> None:
    """
    Load an SVG file, append circles at the given points, and save to a new file.

    Args:
        input_svg_path: Path to the existing SVG file.
        output_svg_path: Path where the annotated SVG will be written.
        points: Iterable of (x, y) tuples to mark.
        radius: Radius of each circle in SVG units. Default is 5.
        color: Fill color for the circles. Default is 'red'.
    """
    # Parse the existing SVG
    tree = ET.parse(input_svg_path)
    root = tree.getroot()

    # Figure out the SVG namespace (usually "http://www.w3.org/2000/svg")
    if root.tag.startswith("{"):
        ns = root.tag[1:root.tag.index("}")]
    else:
        ns = ''
    ET.register_namespace('', ns)  # preserve the default namespace in output

    # Build and append one <circle> element per point
    for x, y in points:
        attrib = {
            'cx': str(x),
            'cy': str(y),
            'r': str(radius),
            'fill': color,
        }
        circle = ET.Element(f'{{{ns}}}circle', attrib)
        root.append(circle)

    # Write the modified tree back out
    tree.write(output_svg_path, encoding='utf-8', xml_declaration=True)


def edge_crossings_bezier(G: nx.Graph, tol: float = 1e-6, return_crossings: bool = False) -> Union[float, Tuple[float, List[Tuple[Tuple[float, float], float]]]]:
    """
    Experimental Bezier-based edge crossing detector.

    Intersects original path segments (including curves) without linearization.
    Returns the edge crossing metric and optionally the list of crossings with
    their angles in degrees. May be considerably slower on large graphs.

    Args:
        G: A NetworkX graph with edge 'path' attributes.
        tol: Tolerance for degenerate segments and endpoint checks.
        return_crossings: If True, also return the list of crossings.

    Returns:
        Either the crossing score in [0, 1], or (score, crossings).
    """

    # Node postions as complex numbers for efficiency
    node_pos = {
        n: complex(data.get('x', 0.0), data.get('y', 0.0))
        for n, data in G.nodes(data=True)
    }


    edges = list(G.edges(data=True))
    paths = [parse_path(d['path']) for (_, _, d) in edges]

    # Keep track of which crossings are computed per edge pair
    seen = {
        (i, j): []
        for i, j in itertools.combinations(range(len(edges)), 2)
    }

    crossings = []
    print("combinations=",sum(1 for ignore in itertools.combinations(edges, 2)))
    count = 0
    # Loop over pairs of edges
    for (i, (u1, v1, d1)), (j, (u2, v2, d2)) in itertools.combinations(enumerate(edges), 2):
        count += 1
        print(count, end='\r')


        # path1 = parse_path(d1['path'])
        # path2 = parse_path(d2['path'])
        path1 = paths[i]
        path2 = paths[j]

        # The true graph‐node endpoints of these two edges
        endpoints = {
            node_pos[u1], node_pos[v1],
            node_pos[u2], node_pos[v2],
        }

        # Check every segment‐pair for intersections
        for seg1, seg2 in itertools.product(path1, path2):
            # Skip 0 length segments
            if abs(seg1.start - seg1.end) < tol or abs(seg2.start - seg2.end) < tol:
                continue
            
            # Skip the same (or exactly overlapping) segments
            if seg1 == seg2:
                continue


            for t1, t2 in seg1.intersect(seg2):
                pt = seg1.point(t1)

                # Skip intersections that occur at an actual node
                if any(abs(pt - ep) < tol for ep in endpoints):
                    continue

                x, y = pt.real, pt.imag

                # Skip if this edge pair already saw a crossing here
                if any(abs(x - xx) < tol and abs(y - yy) < tol
                       for xx, yy in seen[(i, j)]):
                    continue

                # Mark it as seen for this pair
                seen[(i, j)].append((x, y))

                # Compute the acute angle between the two segments
                vec1 = seg1.derivative(t1)
                vec2 = seg2.derivative(t2)
                prod = (abs(vec1)*abs(vec2))
                if prod == 0:
                    continue
                cos_theta = (vec1.real*vec2.real + vec1.imag*vec2.imag) / prod
                cos_theta = max(-1.0, min(1.0, cos_theta))
                theta = math.acos(cos_theta)
                if theta > math.pi/2:
                    theta = math.pi - theta
                angle_deg = math.degrees(theta)

                crossings.append(((x, y), angle_deg))

    # Compute metric value
    m = G.number_of_edges()
    c_all = (m*(m-1)) / 2
    c_deg = sum((G.degree[u]*(G.degree[u]-1)) for u in G) / 2
    c_mx = c_all - c_deg
    c = len(crossings)
    ec = (1 - (c / c_mx)) if c_mx > 0 else 1.0


    if return_crossings:
        return max(0, ec), crossings
    else:
        return max(0, ec)

def bboxes_intersect(p1: Tuple[float, float], p2: Tuple[float, float], p3: Tuple[float, float], p4: Tuple[float, float]) -> bool:
    """
    Test whether the AABB of two segments overlap.

    Args:
        p1, p2: Endpoints of the first segment as (x, y).
        p3, p4: Endpoints of the second segment as (x, y).

    Returns:
        True if the axis-aligned bounding boxes overlap, else False.
    """
    x1_min, x1_max = min(p1[0], p2[0]), max(p1[0], p2[0])
    y1_min, y1_max = min(p1[1], p2[1]), max(p1[1], p2[1])
    x2_min, x2_max = min(p3[0], p4[0]), max(p3[0], p4[0])
    y2_min, y2_max = min(p3[1], p4[1]), max(p3[1], p4[1])

    # No overlap if one box is entirely to one side of the other
    if x1_max < x2_min or x2_max < x1_min:
        return False
    if y1_max < y2_min or y2_max < y1_min:
        return False
    return True

def flatten_path_to_lines(path: Path, samples_per_curve: int = 50) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """
    Convert an svgpathtools Path into a list of straight line segments.

    Real Line segments are kept as-is. Curved segments are sampled into
    'samples_per_curve' points and then turned into consecutive line segments.

    Args:
        path: The svgpathtools Path to flatten.
        samples_per_curve: Number of samples per curved segment.

    Returns:
        List of 2D line segments, each as ((x0, y0), (x1, y1)).
    """
    lines = []
    for seg in path:
        if isinstance(seg, Line):
            # keep the exact straight segment
            lines.append(((seg.start.real, seg.start.imag),
                          (seg.end.real,   seg.end.imag)))
        else:
            # sample the curve at equally spaced t's
            ts = [k/(samples_per_curve - 1) for k in range(samples_per_curve)]
            pts = [seg.point(t) for t in ts]
            for p0, p1 in zip(pts, pts[1:]):
                lines.append(((p0.real, p0.imag),
                              (p1.real, p1.imag)))
    return lines

def check_intersection(p1: Tuple[float, float], p2: Tuple[float, float], p3: Tuple[float, float], p4: Tuple[float, float], tol: float = 1e-9) -> Optional[Tuple[Tuple[float, float], float]]:
    """
    Compute interior intersection of two line segments.

    Args:
        p1, p2: First segment endpoints as (x, y).
        p3, p4: Second segment endpoints as (x, y).
        tol: Numerical tolerance; also used to exclude endpoints.

    Returns:
        None if no interior intersection exists; otherwise ((x, y), angle_deg)
        where angle_deg is the acute angle between the segments in degrees.
    """
    # direction vectors
    r = (p2[0] - p1[0], p2[1] - p1[1])
    s = (p4[0] - p3[0], p4[1] - p3[1])
    # cross(r, s)
    den = r[0]*s[1] - r[1]*s[0]
    if abs(den) < tol:
        return None  # parallel or colinear
    # solve p1 + t r = p3 + u s
    dx = (p3[0] - p1[0], p3[1] - p1[1])
    t = (dx[0]*s[1] - dx[1]*s[0]) / den
    u = (dx[0]*r[1] - dx[1]*r[0]) / den
    # require intersection in interior (exclude endpoints)
    if not (tol < t < 1-tol and tol < u < 1-tol):
        return None
    # intersection point
    ix = p1[0] + t * r[0]
    iy = p1[1] + t * r[1]
    # compute acute angle between r and s
    dot = r[0]*s[0] + r[1]*s[1]
    nr = math.hypot(*r)
    ns = math.hypot(*s)
    if nr < tol or ns < tol:
        return None
    cos_theta = abs(dot / (nr * ns))
    cos_theta = max(-1.0, min(1.0, cos_theta))
    angle_rad = math.acos(cos_theta)
    angle_deg = math.degrees(angle_rad)
    return ((ix, iy), angle_deg)

def edge_crossings(G: nx.Graph, return_crossings: bool = False, samples_per_curve: int = 100, min_angle_tol: float = 2.5) -> Union[float, Tuple[float, List[Tuple[Tuple[float, float], float]]]]:
    """
    Count edge crossings (with linearized curves) and compute a crossing score.

    Each edge path is flattened into straight-line segments. For every pair of
    edges, all segment pairs are tested for intersection using bounding-box
    rejection and exact segment intersection; intersections at endpoints are
    excluded. A minimum angle tolerance filters near-parallel overlaps.

    The score is normalized using an upper bound on crossings c_max = c_all - c_deg,
    where c_all = m(m-1)/2 and c_deg is the sum over nodes of deg(u)(deg(u)-1)/2.
    The returned metric is 1 - c/c_max (or 1.0 if c_max == 0), clamped to >= 0.

    Args:
        G: A NetworkX graph with edge 'path' attributes.
        return_crossings: If True, also return the list of crossings with angles.
        samples_per_curve: Number of samples used to linearize curved segments.
        min_angle_tol: Minimum crossing angle (degrees) to keep a crossing.

    Returns:
        Either the crossing score in [0, 1], or (score, crossings) where each
        crossing is ((x, y), angle_deg).
    """

    edges = list(G.edges(data=True))
    paths = [parse_path(d['path']) for _, _, d in edges]
    polys = [flatten_path_to_lines(p, samples_per_curve) for p in paths]
    
    crossings = []
    
    for (i, (u1, v1, d1)), (j, (u2, v2, d2)) in itertools.combinations(enumerate(edges), 2):

        poly1 = polys[i]
        poly2 = polys[j]

        for (p1, p2) in poly1:
            for (p3, p4) in poly2:
                if not bboxes_intersect(p1, p2, p3, p4):
                    continue

                hit = check_intersection(p1, p2, p3, p4)
                if hit is None:
                    continue

                _, angle = hit
                if angle < min_angle_tol:
                    continue

                crossings.append(hit)
        
    # Compute metric value
    m = G.number_of_edges()
    c_all = (m*(m-1)) / 2
    c_deg = sum((G.degree[u]*(G.degree[u]-1)) for u in G) / 2
    c_mx = c_all - c_deg
    c = len(crossings)
    ec = (1 - (c / c_mx)) if c_mx > 0 else 1.0


    if return_crossings:
        return max(0, ec), crossings
    else:
        return max(0, ec)


