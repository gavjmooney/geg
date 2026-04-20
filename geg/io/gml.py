"""GML → GEG converter.

GML (Graph Modelling Language) is handled via `networkx.read_gml`. yEd and
other tools store drawing attributes under a `graphics` dict per node/edge;
this module unpacks the common fields into GEG-canonical attribute names.
"""

from typing import Optional

import networkx as nx

from .geg import write_geg


def _copy_node_attrs(src_attrs: dict) -> dict:
    """Map a GML node's attributes onto GEG-canonical ones."""
    g = src_attrs.get("graphics", {}) or {}
    try:
        x = float(g.get("x", 0))
        y = float(g.get("y", 0))
    except (TypeError, ValueError):
        x, y = 0.0, 0.0
    out = {"x": x, "y": y, "position": [x, y]}

    if "fill" in g:
        out["colour"] = g["fill"]
    if "type" in g:
        out["shape"] = g["type"]
    if "w" in g:
        try:
            out["width"] = float(g["w"])
        except (TypeError, ValueError):
            pass
    if "h" in g:
        try:
            out["height"] = float(g["h"])
        except (TypeError, ValueError):
            pass

    # GML often carries a top-level `label`.
    if "label" in src_attrs:
        out["label"] = src_attrs["label"]
    return out


def _copy_edge_attrs(src_attrs: dict, x0: float, y0: float, x1: float, y1: float) -> dict:
    """Map a GML edge's attributes onto GEG-canonical ones, including path."""
    g = src_attrs.get("graphics", {}) or {}
    points = g.get("Line", {}).get("point", []) if isinstance(g, dict) else []

    # Deduplicate consecutive identical bends.
    cleaned: list = []
    prev = None
    for p in points:
        try:
            current = (float(p["x"]), float(p["y"]))
        except (TypeError, ValueError, KeyError):
            continue
        if current != prev:
            cleaned.append(current)
        prev = current
    points = cleaned

    poly = bool(g.get("smoothBends", 0)) or len(points) > 2
    if len(points) < 2:
        path = f"M{x0},{y0} L{x1},{y1}"
    else:
        segs = [f"M{points[0][0]},{points[0][1]}"]
        segs += [f"L{bx},{by}" for bx, by in points[1:]]
        path = " ".join(segs)

    out: dict = {"polyline": poly, "path": path}

    if isinstance(g, dict):
        if "fill" in g:
            out["colour"] = g["fill"]
        if "width" in g:
            try:
                out["stroke_width"] = float(g["width"])
            except (TypeError, ValueError):
                pass

    if "label" in src_attrs:
        out["label"] = src_attrs["label"]
    if "weight" in src_attrs:
        try:
            out["weight"] = float(src_attrs["weight"])
        except (TypeError, ValueError):
            pass
    return out


def gml_to_geg(input_file: str, output_file: Optional[str] = None) -> nx.Graph:
    """Convert a GML drawing to a GEG NetworkX graph.

    Preserves node position, dimensions (`width`, `height`), colour, shape,
    and label when present; edge bends, colour, stroke-width, label, and
    weight when present. Optionally writes the result to `output_file` as
    GEG JSON.
    """
    G = nx.read_gml(input_file, label=None)

    if G.is_multigraph():
        H: nx.Graph = nx.MultiDiGraph() if G.is_directed() else nx.MultiGraph()
    else:
        H = nx.DiGraph() if G.is_directed() else nx.Graph()
    H.graph.update(G.graph)

    # Pre-extract node positions so edges can reference endpoints.
    for n, attrs in G.nodes(data=True):
        H.add_node(n, **_copy_node_attrs(attrs))

    for u, v, attrs in G.edges(data=True):
        x0, y0 = H.nodes[u]["x"], H.nodes[u]["y"]
        x1, y1 = H.nodes[v]["x"], H.nodes[v]["y"]
        H.add_edge(u, v, **_copy_edge_attrs(attrs, x0, y0, x1, y1))

    if output_file:
        write_geg(H, output_file)
    return H
