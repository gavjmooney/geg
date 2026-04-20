# GEG Encodes Graphs is a file format designed by Gavin J. Mooney.
# It is based on JSON and stores graph drawings with attrbiutes,
# including curved edges which follow the SVG path format.
# https://www.gavjmooney.com

"""Geometry, rendering, and curves-promotion helpers for GEG drawings.

File-I/O functions live in `geg.io` as of the Phase 5 refactor. The
re-exports below keep existing imports like
`from geg.geg_parser import read_geg` working for downstream callers.
"""

import math
import re
import xml.dom.minidom
from typing import Any, Dict, Hashable, Iterable, List, Optional, Tuple, Union
from xml.etree.ElementTree import Element, SubElement, tostring

import networkx as nx
import numpy as np
import svgpathtools
from scipy.spatial import ConvexHull
from scipy.spatial.distance import pdist

# Re-exports: file I/O (public API entry points) now live under geg.io.
from .io.geg import (
    _coerce_bool,
    has_self_loops_file,
    is_multigraph_file,
    read_geg,
    write_geg,
)
from .io.gml import gml_to_geg
from .io.graphml import graphml_to_geg


def get_convex_hull_area(G: nx.Graph, tol: float = 1e-6) -> float:
    """
    Compute the area of the convex hull of the promoted drawing.

    Promotes curved edges into polylines to ensure the hull encloses all drawn
    geometry, then computes the 2D hull area.

    Args:
        G: A NetworkX graph with node coordinates 'x' and 'y'.
        tol: Numerical tolerance for rank estimation.

    Returns:
        The convex-hull area as a float. For degenerate cases (n < 3 or
        collinear points), returns the maximum pairwise distance instead.
    """
    H = curves_promotion(G)
    points = [(H.nodes[n]['x'], H.nodes[n]['y']) for n in H.nodes()]
    pts = np.asarray(points, dtype=float)

    n = len(points)

    if n == 1:
        return 1
    if n < 3:
        return np.max(pdist(pts))
    
    vectors = pts - pts[0]
    rank = np.linalg.matrix_rank(vectors, tol)
    if rank <= 1:
        return np.max(pdist(pts))


    hull = ConvexHull(pts)
    # In 2D, hull.volume is the enclosed area; hull.area would be the perimeter
    return hull.volume

def euclidean_distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """
    Euclidean distance between 2D points a and b.
    """
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    return math.hypot(dx, dy)

def has_self_loops_graph(G: nx.Graph) -> bool:
    """Return True if the graph contains any self-loop edges."""
    for u, v in G.edges():
        if u == v:
            return True
    return False


def is_multigraph_graph(G: nx.Graph) -> bool:
    """Return True iff G is a NetworkX MultiGraph or MultiDiGraph."""
    return isinstance(G, (nx.MultiGraph, nx.MultiDiGraph))


def contains_curves(G: nx.Graph) -> bool:
    """
    Check if any edge path contains curved commands (non M/L).
    """
    # Iterate over each edge
    for u, v, data in G.edges(data=True):
        path_str = data.get('path', '')
        commands = re.findall(r'[a-zA-Z]', path_str)
        for cmd in commands:
            if cmd.upper() not in {'M', 'L'}:
                return True
    return False


def contains_straight_bends(G: nx.Graph) -> bool:
    found_bend = False

    for u, v, data in G.edges(data=True):
        path_str = data.get('path', '')
        commands = re.findall(r'[a-zA-Z]', path_str)
        upper_commands = [cmd.upper() for cmd in commands]

        # If any edge has a curved command, the whole graph is disqualified
        if any(cmd not in {'M', 'L'} for cmd in upper_commands):
            return False

        if upper_commands.count('L') > 1:
            found_bend = True

    return found_bend




def contains_polylines(G: nx.Graph) -> bool:
    """
    Return True if any edge path encodes a polyline or curve.

    Straight lines are exactly ['M', 'L']. Any additional commands (extra L's,
    Q/C/S/T, Z, etc.) are considered polylines/curves.
    """

    for u, v, data in G.edges(data=True):
        path_str = data.get("path", "")
        # extract all SVG command letters
        commands = re.findall(r"([MLQCSTVHZ])", path_str)
        # straight iff exactly ['M','L']
        if commands != ["M", "L"]:
            return True
    return False




def get_bounding_box(G: nx.Graph, promote: bool = True) -> Tuple[float, float, float, float]:
    """
    Compute the axis-aligned bounding box of the drawing.

    If promote=True, curves are exploded to ensure the box encloses their
    geometry; only the original nodes/edges are still drawn elsewhere.

    Args:
        G: The input graph with coordinates.
        promote: Whether to include curve-promoted segment nodes.

    Returns:
        A tuple (min_x, min_y, max_x, max_y).
    """
    # Promote curves so that all segment‐nodes are included
    if promote:
        H = curves_promotion(G)
        xs = [data['x'] for _, data in H.nodes(data=True)]
        ys = [data['y'] for _, data in H.nodes(data=True)]
    else:
        xs = [data['x'] for _, data in G.nodes(data=True)]
        ys = [data['y'] for _, data in G.nodes(data=True)]

    if not xs or not ys:
        # Empty graph
        return 0.0, 0.0, 0.0, 0.0

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    return min_x, min_y, max_x, max_y

def _scale_path(path_str: str, scale: float) -> str:
    """Scale numeric coordinates in an SVG path 'd' string by `scale`.

    Keeps command letters (M/L/C/Q/S/T/A/H/V/Z, upper and lower) intact and
    multiplies each numeric literal by `scale`.
    """
    pattern = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")

    def repl(m: re.Match) -> str:
        return f"{float(m.group(0)) * scale:g}"

    return pattern.sub(repl, path_str)


def to_svg(
    G: nx.Graph,
    output_file: str,
    *,
    margin: float = 50.0,
    scale: float = 50.0,
    grid: bool = False,
    node_radius: float = 10.0,
    stroke_width: float = 2.0,
    grid_stroke: str = "#ddd",
    grid_stroke_width: float = 0.5,
) -> None:
    """Render a drawing to SVG in pixel coordinates.

    GEG coordinates are multiplied by `scale` (pixels per GEG unit) so that
    unit-scale fixtures render at a readable size. `margin` is in pixels and
    is applied around the (scaled) bounding box of the curve-promoted drawing.

    Args:
        G: NetworkX graph with node 'x'/'y' and optional edge 'path' attrs.
        output_file: Output SVG filename.
        margin: Padding around the bounding box, in pixels.
        scale: Pixels per GEG unit.
        grid: If True, draw a faint integer-GEG-coordinate grid behind the
            drawing. Intended for fixtures that need manual verification.
        node_radius: Default node radius, in pixels (overridden by per-node
            'radius' / 'size' attrs).
        stroke_width: Edge and node outline width, in pixels.
        grid_stroke: Stroke colour for grid lines.
        grid_stroke_width: Stroke width for grid lines, in pixels.
    """
    min_x, min_y, max_x, max_y = get_bounding_box(G)

    # Work in pixel coordinates: scale GEG coords, then add the pixel-margin
    # around the scaled bbox.
    sx_min = min_x * scale
    sy_min = min_y * scale
    sx_max = max_x * scale
    sy_max = max_y * scale
    vb_x = sx_min - margin
    vb_y = sy_min - margin
    vb_w = (sx_max - sx_min) + 2 * margin
    vb_h = (sy_max - sy_min) + 2 * margin

    svg = Element(
        "svg",
        xmlns="http://www.w3.org/2000/svg",
        version="1.1",
        width=str(vb_w),
        height=str(vb_h),
        viewBox=f"{vb_x} {vb_y} {vb_w} {vb_h}",
    )

    if "description" in G.graph:
        desc = SubElement(svg, "desc")
        desc.text = G.graph["description"]

    # 1. Grid — rendered first so edges/nodes paint on top.
    if grid:
        grid_group = SubElement(svg, "g", attrib={"class": "grid"})
        # Integer x lines spanning the y-range.
        x_lo = math.ceil(min_x)
        x_hi = math.floor(max_x)
        for gx in range(x_lo, x_hi + 1):
            SubElement(
                grid_group, "line",
                x1=str(gx * scale), y1=str(vb_y),
                x2=str(gx * scale), y2=str(vb_y + vb_h),
                stroke=grid_stroke, attrib={"stroke-width": str(grid_stroke_width)},
            )
        y_lo = math.ceil(min_y)
        y_hi = math.floor(max_y)
        for gy in range(y_lo, y_hi + 1):
            SubElement(
                grid_group, "line",
                x1=str(vb_x), y1=str(gy * scale),
                x2=str(vb_x + vb_w), y2=str(gy * scale),
                stroke=grid_stroke, attrib={"stroke-width": str(grid_stroke_width)},
            )

    # 2. Edges.
    for u, v, attrs in G.edges(data=True):
        path_str = attrs.get("path")
        if path_str:
            d = _scale_path(path_str, scale)
        else:
            x0 = G.nodes[u]["x"] * scale
            y0 = G.nodes[u]["y"] * scale
            x1 = G.nodes[v]["x"] * scale
            y1 = G.nodes[v]["y"] * scale
            d = f"M{x0:g},{y0:g} L{x1:g},{y1:g}"
        path_elem = SubElement(
            svg, "path",
            d=d,
            fill="none",
            stroke=attrs.get("colour", "black"),
            attrib={"stroke-width": str(stroke_width)},
        )
        if "id" in attrs:
            path_elem.set("id", attrs["id"])

    # 3. Nodes.
    for node, attrs in G.nodes(data=True):
        cx = attrs["x"] * scale
        cy = attrs["y"] * scale
        fill = attrs.get("colour", "#FFFFFF")
        shape = attrs.get("shape", "ellipse").lower()
        if shape in ("ellipse", "circle"):
            r = attrs.get("radius", node_radius)
            node_elem = SubElement(
                svg, "ellipse",
                cx=str(cx), cy=str(cy), rx=str(r), ry=str(r),
                fill=fill, stroke="black",
                attrib={"stroke-width": str(stroke_width)},
            )
        elif shape in ("square", "rectangle", "rect"):
            size = attrs.get("size", node_radius * 2)
            half = size / 2
            node_elem = SubElement(
                svg, "rect",
                x=str(cx - half), y=str(cy - half),
                width=str(size), height=str(size),
                fill=fill, stroke="black",
                attrib={"stroke-width": str(stroke_width)},
            )
        else:
            node_elem = SubElement(
                svg, "circle",
                cx=str(cx), cy=str(cy), r=str(node_radius),
                fill=fill, stroke="black",
                attrib={"stroke-width": str(stroke_width)},
            )
        node_elem.set("id", str(node))

    raw = tostring(svg, "utf-8")
    pretty = xml.dom.minidom.parseString(raw).toprettyxml(indent="  ")
    with open(output_file, "w") as f:
        f.write(pretty)

def compute_global_scale(G: nx.Graph, target_segments: int = 10) -> float:
    """
    Compute a unit length so the bounding-box diagonal is split into N pieces.

    Args:
        G: Input graph.
        target_segments: Desired number of pieces along the diagonal.

    Returns:
        The target unit length (defaults to 1.0 for degenerate boxes).
    """
    xs = [data['x'] for _, data in G.nodes(data=True)]
    ys = [data['y'] for _, data in G.nodes(data=True)]
    dx = max(xs) - min(xs)
    dy = max(ys) - min(ys)
    diag = math.hypot(dx, dy)
    # This is the desired length of each little piece:
    return diag / target_segments if diag > 0 else 1.0


def determine_N_for_segment(G: nx.Graph, segment: Any, target_segments: int = 10, min_samples: int = 4, max_samples: int = 500) -> int:
    """
    Choose subdivision count for one path segment based on global scale.

    Args:
        G: Input graph for scale computation.
        segment: An svgpathtools segment (Line/Bezier/etc.).
        target_segments: Target number of diagonal pieces for global scale.
        min_samples: Minimum allowed samples per segment (not enforced here).
        max_samples: Maximum allowed samples per segment (not enforced here).

    Returns:
        The chosen number of subsegments N for this segment.
    """
    global_scale = compute_global_scale(G, target_segments)
    seg_len = segment.length(error=1e-5)  # svgpathtools length()
    # number of pieces = ceil(total_length / piece_length)
    N = math.ceil(seg_len / global_scale)
    
    return N
    # return max(min_samples, min(N, max_samples))


def approximate_edge_polyline(G: nx.Graph, edge: Tuple[Hashable, Hashable, Dict[str, Any]], global_segments_N: int = 10) -> List[Tuple[float, float]]:
    """
    Linearize an edge's SVG path into a polyline of sample points.

    Args:
        G: Input graph for scale and node positions.
        edge: A tuple (u, v, attrs) describing the edge.
        global_segments_N: Global scale target for sampling density.

    Returns:
        A list of (x, y) points including endpoints.
    """
    u, v, attrs = edge
    x0, y0 = G.nodes[u]['x'], G.nodes[u]['y']
    x1, y1 = G.nodes[v]['x'], G.nodes[v]['y']

    path_str = attrs.get('path', None)
    if not path_str:
        return [(x0, y0), (x1, y1)]

    path = svgpathtools.parse_path(path_str)
    poly = []
    for seg in path:
        if isinstance(seg, svgpathtools.Line):
            pts = [
                (seg.start.real, seg.start.imag),
                (seg.end.real,   seg.end.imag)
            ]
        else:
            # pick N based on global and local geometry
            N = determine_N_for_segment(G, seg, target_segments=global_segments_N)
            pts = [
                (seg.point(t).real, seg.point(t).imag)
                for t in (i / N for i in range(N + 1))
            ]

        if not poly:
            poly.extend(pts)
        else:
            poly.extend(pts[1:])

    # snap endpoints exactly to node positions
    if poly:
        poly[0]  = (x0, y0)
        poly[-1] = (x1, y1)
    return poly

def curves_promotion(G: nx.Graph, global_segments_N: int = 10) -> nx.Graph:
    """
    Promote curved/polyline edges by splitting them into straight segments.

    Produces a new graph H with the same type as G. Original nodes/edges are
    copied with is_segment=False. Each curve is approximated with intermediate
    nodes (is_segment=True) connected by straight segments encoded as M/L paths.

    Args:
        G: Input graph with edge 'path' attributes.
        global_segments_N: Sampling density used for approximation.

    Returns:
        A new graph H with promoted segments.
    """
    # Make H of the same type as G
    if G.is_multigraph():
        H = nx.MultiDiGraph() if G.is_directed() else nx.MultiGraph()
    else:
        H = nx.DiGraph()       if G.is_directed() else nx.Graph()

    # Copy graph-level attributes
    H.graph.update(G.graph)

    # Copy original nodes
    for n, attrs in G.nodes(data=True):
        a = attrs.copy()
        a['is_segment'] = False
        H.add_node(n, **a)

    # Process each edge
    for u, v, attrs in G.edges(data=True):
        eid   = attrs.get('id', f"{u}-{v}")
        poly  = attrs.get('polyline', False)

        # Copy straight-line edges untouched
        if not poly:
            a = attrs.copy()
            a['is_segment'] = False
            H.add_edge(u, v, **a)
            continue

        # Explode a curved/polyline edge
        pts = approximate_edge_polyline(G, (u, v, attrs), global_segments_N)
        # pts[0] and pts[-1] have already been snapped to (u,v)

        # If the interior is “backwards,” flip it:
        if len(pts) > 2:
            x0, y0 = G.nodes[u]['x'], G.nodes[u]['y']
            x1, y1 = G.nodes[v]['x'], G.nodes[v]['y']
            px, py = pts[1]   # first interior sample
            # if that sample is closer to v than to u, we’re reversed
            if math.hypot(px - x0, py - y0) > math.hypot(px - x1, py - y1):
                interior = pts[1:-1][::-1]
                pts = [(x0, y0)] + interior + [(x1, y1)]

        # Build the node-sequence [u, seg1, seg2, …, v]
        node_seq = [u]
        for i, (x, y) in enumerate(pts[1:-1], start=1):
            seg_n = f"{eid}_pt_{i}"
            H.add_node(seg_n, x=float(x), y=float(y), is_segment=True)
            node_seq.append(seg_n)
        node_seq.append(v)

        # Link each consecutive pair with a straight-line SVG path
        for i in range(len(node_seq) - 1):
            a, b = node_seq[i], node_seq[i+1]
            x0, y0 = H.nodes[a]['x'], H.nodes[a]['y']
            x1, y1 = H.nodes[b]['x'], H.nodes[b]['y']
            path_str = f"M{x0},{y0} L{x1},{y1}"
            seg_attrs = {
                'id':         f"{eid}_seg_{i+1}",
                'is_segment': True,
                'path':       path_str
            }
            H.add_edge(a, b, **seg_attrs)

    return H



    