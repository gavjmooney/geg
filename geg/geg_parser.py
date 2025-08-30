# GEG Encodes Graphs is a file format designed by Gavin J. Mooney.
# It is based on JSON and stores graph drawings with attrbiutes,
# including curved edges which follow the SVG path format.
# https://www.gavjmooney.com

import json
import re
import networkx as nx
import math
import json
import svgpathtools
from . import parse_graph as pg
import numpy as np
from scipy.spatial import ConvexHull
from xml.etree.ElementTree import Element, SubElement, tostring
import xml.dom.minidom
from scipy.spatial.distance import pdist
from typing import Any, Dict, Hashable, Iterable, List, Optional, Tuple, Union

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

def has_self_loops_file(input_file: str) -> bool:
    """
    Determine whether the GEG file contains any self-loops.

    Args:
        input_file: Path to a .geg JSON file.

    Returns:
        True if any edge has the same source and target, else False.
    """
    with open(input_file, 'r') as f:
        data = json.load(f)

    for edge in data.get("edges", []):
        if edge["source"] == edge["target"]:
            return True

    return False

def has_self_loops_graph(G: nx.Graph) -> bool:
    """Return True if the graph contains any self-loop edges."""
    for u, v in G.edges():
        if u == v:
            return True
    return False

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

def is_multigraph_file(input_file: str) -> bool:
    """
    Determine whether the GEG file represents a multigraph.

    Detects multiple edges between the same pair (normalized if undirected).

    Args:
        input_file: Path to the .geg file.

    Returns:
        True if any pair of nodes has more than one edge between them.
    """
    with open(input_file, 'r') as f:
        data = json.load(f)

    directed = data.get("graph", {}).get("directed", False)
    seen = {}
    for edge in data.get("edges", []):
        src = edge["source"]
        tgt = edge["target"]
        # For undirected graphs, normalize the key
        key = (src, tgt) if directed else tuple(sorted((src, tgt)))
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            return True#, seen

    return False#, seen

def is_multigraph_graph(G: nx.Graph) -> bool:
    """Return True if G is a NetworkX MultiGraph or MultiDiGraph."""
    return isinstance(G, (nx.MultiGraph, nx.MultiDiGraph))

def read_geg(input_file: str) -> nx.Graph:
    """
    Read a GEG file into a NetworkX graph, preserving attributes.

    Accepts node coordinates as 'position' (list/tuple or {'x','y'}), 'pos', or
    top-level 'x'/'y', and normalizes nodes to always have 'x','y','position'.

    Args:
        input_file: Path to the .geg JSON file.

    Returns:
        A NetworkX Graph/DiGraph/Multi(Graph/DiGraph) mirroring the input.
    """
    with open(input_file, "r") as file:
        data = json.load(file)

    if is_multigraph_file(input_file):
        G = nx.MultiDiGraph() if data["graph"].get("directed", False) else nx.MultiGraph()
    else:
        # Create a directed or undirected graph
        G = nx.DiGraph() if data["graph"].get("directed", False) else nx.Graph()

    # Store graph-level properties (metadata)
    G.graph.update({k: v for k, v in data["graph"].items() if k != "directed"})

    # Add nodes
    for node in data["nodes"]:
        node_id = node["id"]
        attrs = {k: v for k, v in node.items() if k != "id"}

        # Normalize position: accept 'pos', 'position', or top-level 'x'/'y'
        x_val = None
        y_val = None

        # Case 1: explicit x/y
        if 'x' in attrs and 'y' in attrs:
            try:
                x_val = float(attrs['x'])
                y_val = float(attrs['y'])
            except Exception:
                pass

        # Case 2: 'pos' as list/tuple or dict
        if (x_val is None or y_val is None) and 'pos' in attrs:
            pos = attrs.get('pos')
            try:
                if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                    x_val = float(pos[0])
                    y_val = float(pos[1])
                elif isinstance(pos, dict) and 'x' in pos and 'y' in pos:
                    x_val = float(pos['x'])
                    y_val = float(pos['y'])
            except Exception:
                pass

        # Case 3: 'position' as list/tuple or dict
        if (x_val is None or y_val is None) and 'position' in attrs:
            position = attrs.get('position')
            try:
                if isinstance(position, (list, tuple)) and len(position) >= 2:
                    x_val = float(position[0])
                    y_val = float(position[1])
                elif isinstance(position, dict) and 'x' in position and 'y' in position:
                    x_val = float(position['x'])
                    y_val = float(position['y'])
            except Exception:
                pass

        # If we got coordinates, ensure both x/y and position are present
        if x_val is not None and y_val is not None:
            attrs['x'] = x_val
            attrs['y'] = y_val
            attrs['position'] = [x_val, y_val]

        G.add_node(node_id, **attrs)

    # Add edges
    for edge in data["edges"]:
        edge_id = edge["id"]
        source = edge["source"]
        target = edge["target"]
        edge_attributes = {k: v for k, v in edge.items() if k not in ["id"]}#, "source", "target"]}
        G.add_edge(source, target, id=edge_id, **edge_attributes)

    return G

def write_geg(G: nx.Graph, output_file: str) -> None:
    """
    Write a NetworkX graph to the GEG JSON file format.

    Ensures each node includes a 'position' array (built from x/y or pos).

    Args:
        G: The NetworkX graph to save.
        output_file: Path to write the .geg file.
    """
    geg_data = {
        "graph": {
            "directed": isinstance(G, nx.DiGraph),
            **G.graph  # Include any other graph-level properties
        },
        "nodes": [],
        "edges": []
    }

    # Convert nodes
    for node, attrs in G.nodes(data=True):
        node_data = {"id": node, **attrs}
        # Ensure 'position' exists, building from x/y if necessary
        if 'position' not in node_data:
            x_val = node_data.get('x', None)
            y_val = node_data.get('y', None)
            if x_val is None or y_val is None:
                pos = node_data.get('pos', None)
                if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                    x_val, y_val = pos[0], pos[1]
                elif isinstance(pos, dict) and 'x' in pos and 'y' in pos:
                    x_val, y_val = pos['x'], pos['y']
            if x_val is not None and y_val is not None:
                try:
                    node_data['position'] = [float(x_val), float(y_val)]
                except Exception:
                    pass
        geg_data["nodes"].append(node_data)

    # Convert edges
    for source, target, attrs in G.edges(data=True):
        edge_data = {"id": attrs.get("id", f"{source}-{target}"), "source": source, "target": target}
        edge_data.update({k: v for k, v in attrs.items() if k != "id"})  # Preserve edge properties
        geg_data["edges"].append(edge_data)

    # Write to file
    with open(output_file, "w") as file:
        json.dump(geg_data, file, indent=4)
        

def gml_to_geg(input_file: str, output_file: Optional[str] = None) -> nx.Graph:
    """
    Convert a yEd-style GML drawing to a GEG graph.

    Reads node positions and bend points into a NetworkX graph; optionally
    writes a .geg file.

    Args:
        input_file: Path to the .gml file.
        output_file: Optional path to write the converted .geg file.

    Returns:
        The converted NetworkX graph.
    """
    G = nx.read_gml(input_file, label=None)

    if G.is_multigraph():
        H = nx.MultiDiGraph() if G.is_directed() else nx.MultiGraph()
    else:
        H = nx.DiGraph() if G.is_directed() else nx.Graph()

    H.graph.update(G.graph)

    for n, attrs in G.nodes(data=True):
        g = attrs.get('graphics', {})
        x, y = float(g.get('x', 0)), float(g.get('y', 0))
        node_attrs = {'position': [x, y]}
        node_attrs['x'], node_attrs['y'] = x, y

        if 'fill' in g:
            node_attrs['colour'] = g['fill']
        if 'type' in g:
            node_attrs['shape'] = g['type']

        H.add_node(n, **node_attrs)

    for u, v, attrs in G.edges(data=True):
        g = attrs.get('graphics', {})
        points = g.get('Line', {}).get('point', [])
        poly = bool(g.get('smoothBends', 0))

        # Get fallback endpoints
        x0, y0 = float(G.nodes[u]['graphics']['x']), float(G.nodes[u]['graphics']['y'])
        x1, y1 = float(G.nodes[v]['graphics']['x']), float(G.nodes[v]['graphics']['y'])

        # remove duplicate bend points
        cleaned_points = []
        prev = None
        for p in points:
            current = (float(p['x']), float(p['y']))
            if current != prev:
                cleaned_points.append(p)
            prev = current

        points = cleaned_points

        # Build SVG path
        if not points:
            path = f"M{x0},{y0} L{x1},{y1}"
        elif len(points) == 1:
            path = f"M{x0},{y0} L{x1},{y1}"
        else:
            segs = [f"M{points[0]['x']},{points[0]['y']}"]
            segs += [f"L{p['x']},{p['y']}" for p in points[1:]]
            path = " ".join(segs)

        # path = clean_svg_path(path)

        edge_attrs = {
            'polyline': poly,
            'path': path
        }

        H.add_edge(u, v, **edge_attrs)

    if output_file:
        write_geg(H, output_file)
    return H


def graphml_to_geg(input_file: str, output_file: Optional[str] = None) -> nx.Graph:
    """
    Convert a GraphML drawing to a GEG graph.

    Uses the local GraphML reader to preserve drawing attributes; optionally
    writes a .geg file.

    Args:
        input_file: Path to the .graphml file.
        output_file: Optional path to write the converted .geg file.

    Returns:
        The converted NetworkX graph.
    """

    G = pg.read_graphml(input_file)

    
    if G.is_multigraph():
        H = nx.MultiDiGraph() if G.is_directed() else nx.MultiGraph()
    else:
        H = nx.DiGraph()       if G.is_directed() else nx.Graph()

    # copy graph‐level metadata
    H.graph.update(G.graph)


    for n, attrs in G.nodes(data=True):
        x, y = attrs['x'], attrs['y']
        node_attrs = {
            'position': [x, y]
        }
        node_attrs['x'], node_attrs['y'] = x, y

        if 'color' in attrs:
            node_attrs['colour'] = attrs['color']
        # preserve shape
        if 'shape' in attrs:
            node_attrs['shape'] = attrs['shape']
        H.add_node(n, **node_attrs)


    for u, v, attrs in G.edges(data=True):
        poly = bool(attrs.get('polyline', False))
        bends = attrs.get('bends', [])
        # convert any string coords to floats
        pts = []
        for bx, by in bends:
            pts.append((float(bx), float(by)))

        # endpoints
        x0, y0 = G.nodes[u]['x'], G.nodes[u]['y']
        x1, y1 = G.nodes[v]['x'], G.nodes[v]['y']

        # build the SVG path
        if not poly:
            path = f"M{x0},{y0} L{x1},{y1}"
        else:
            segs = [f"M{x0},{y0}"]
            for bx, by in pts:
                segs.append(f"L{bx},{by}")
            segs.append(f"L{x1},{y1}")
            path = " ".join(segs)

        # create the attrs for H
        edge_attrs = {
            'polyline': poly,
            'path': path
        }

        if 'id' in attrs:
            edge_attrs['id'] = attrs['id']

        H.add_edge(u, v, **edge_attrs)

    if output_file:
        write_geg(H, output_file)
    return H



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

def to_svg(G: nx.Graph, output_file: str, margin: float = 50) -> None:
    """
    Render the graph drawing to an SVG file.

    The viewBox is computed from the curve-promoted geometry to avoid clipping
    curved edges, while only original nodes and edges from G are drawn.

    Args:
        G: The input graph with node coordinates and edge paths.
        output_file: Output SVG filename.
        margin: Padding added around the bounding box.
    """
    # Compute bounding box + margin from the promoted graph

    min_x, min_y, max_x, max_y = get_bounding_box(G)

    width  = (max_x - min_x) + 2 * margin
    height = (max_y - min_y) + 2 * margin 
    viewBox = f"{min_x - margin} {min_y - margin} {width} {height}"

    # Create SVG root
    svg = Element(
        'svg',
        xmlns="http://www.w3.org/2000/svg",
        version="1.1",
        width=str(width),
        height=str(height),
        viewBox=viewBox
    )

    # Optional: embed a description
    if 'description' in G.graph:
        desc = SubElement(svg, 'desc')
        desc.text = G.graph['description']

    # Draw edges from the original G
    for u, v, attrs in G.edges(data=True):
        d = attrs.get('path')
        if not d:
            x0, y0 = G.nodes[u]['x'], G.nodes[u]['y']
            x1, y1 = G.nodes[v]['x'], G.nodes[v]['y']
            d = f"M{x0},{y0} L{x1},{y1}"

        path_elem = SubElement(svg, 'path',
                               d=d,
                               fill="none",
                               stroke=attrs.get('colour', 'black'))
        if 'id' in attrs:
            path_elem.set('id', attrs['id'])

    # Draw nodes from the original G
    for node, attrs in G.nodes(data=True):
        x, y = attrs['x'], attrs['y']
        fill  = attrs.get('colour', '#FFFFFF')
        shape = attrs.get('shape', 'ellipse').lower()

        if shape in ('ellipse', 'circle'):
            r = attrs.get('radius', 10)
            node_elem = SubElement(
                svg, 'ellipse',
                cx=str(x), cy=str(y),
                rx=str(r), ry=str(r),
                fill=fill, stroke="black"
            )

        elif shape in ('square', 'rectangle', 'rect'):
            size = attrs.get('size', 20)
            half = size / 2
            node_elem = SubElement(
                svg, 'rect',
                x=str(x - half), y=str(y - half),
                width=str(size), height=str(size),
                fill=fill, stroke="black"
            )

        else:
            # fallback to a circle
            r = attrs.get('radius', 10)
            node_elem = SubElement(
                svg, 'circle',
                cx=str(x), cy=str(y),
                r=str(r), fill=fill, stroke="black"
            )

        node_elem.set('id', str(node))

    # Pretty‐print + save
    raw = tostring(svg, 'utf-8')
    pretty = xml.dom.minidom.parseString(raw).toprettyxml(indent="  ")
    with open(output_file, 'w') as f:
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



    