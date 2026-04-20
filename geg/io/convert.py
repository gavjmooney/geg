"""Format conversion: dispatcher + pair-wise converters.

Single home for converting between the supported drawing formats. Two
layers:

    - `convert(src, dst, **kwargs)` / `read_drawing(path)` /
      `write_drawing(G, path, **kwargs)` — generic dispatchers that pick
      the reader / writer from the file extension. Use these when the
      format is known at runtime, or when you want a one-liner like
      `convert("a.gml", "a.svg")`.

    - `gml_to_geg`, `graphml_to_geg`, `convert_gml_to_graphml`,
      `convert_graphml_to_gml` — explicit pair-wise converters for
      callers that already know both formats.

Supported input extensions: .geg, .graphml, .gml
Supported output extensions: .geg, .graphml, .gml, .svg
"""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, Optional

import networkx as nx

from .geg import read_geg, write_geg
from .gml import read_gml, write_gml
from .graphml import read_graphml, write_graphml


# ---------- Format-specific converters ----------

def graphml_to_geg(input_file: str, output_file: Optional[str] = None) -> nx.Graph:
    """Convert a yEd GraphML drawing to a GEG-canonical NetworkX graph.

    Reads via `read_graphml`, preserves node geometry/colour/shape/label/width/
    height, encodes edge bends as an SVG `M…L…` path, and copies line styling
    and labels forward. Optionally writes the resulting graph to `output_file`
    as GEG JSON.
    """
    G = read_graphml(input_file)

    if G.is_multigraph():
        H: nx.Graph = nx.MultiDiGraph() if G.is_directed() else nx.MultiGraph()
    else:
        H = nx.DiGraph() if G.is_directed() else nx.Graph()
    H.graph.update(G.graph)

    for n, attrs in G.nodes(data=True):
        x = attrs.get("x", 0.0)
        y = attrs.get("y", 0.0)
        node_attrs = {"x": x, "y": y, "position": [x, y]}
        for key in ("width", "height", "colour", "shape", "label"):
            if key in attrs:
                node_attrs[key] = attrs[key]
        H.add_node(n, **node_attrs)

    for u, v, attrs in G.edges(data=True):
        polyline_flag = bool(attrs.get("polyline", False))
        bends = [(float(bx), float(by)) for bx, by in attrs.get("bends", [])]

        x0, y0 = G.nodes[u]["x"], G.nodes[u]["y"]
        x1, y1 = G.nodes[v]["x"], G.nodes[v]["y"]
        if not polyline_flag or not bends:
            path = f"M{x0},{y0} L{x1},{y1}"
        else:
            segs = [f"M{x0},{y0}"]
            segs += [f"L{bx},{by}" for bx, by in bends]
            segs.append(f"L{x1},{y1}")
            path = " ".join(segs)

        edge_attrs = {"polyline": polyline_flag, "path": path}
        for key in ("colour", "stroke_width", "label", "weight", "id"):
            if key in attrs:
                edge_attrs[key] = attrs[key]
        H.add_edge(u, v, **edge_attrs)

    if output_file:
        write_geg(H, output_file)
    return H


def gml_to_geg(input_file: str, output_file: Optional[str] = None) -> nx.Graph:
    """Convert a yEd GML drawing to a GEG-canonical NetworkX graph.

    Reads via `read_gml`, then rewrites edge bends as SVG `M…L…` paths and
    adds a `position` list per node. Optionally writes the result to
    `output_file` as GEG JSON.
    """
    G = read_gml(input_file)

    if G.is_multigraph():
        H: nx.Graph = nx.MultiDiGraph() if G.is_directed() else nx.MultiGraph()
    else:
        H = nx.DiGraph() if G.is_directed() else nx.Graph()
    H.graph.update(G.graph)

    for n, attrs in G.nodes(data=True):
        x = attrs.get("x", 0.0)
        y = attrs.get("y", 0.0)
        node_attrs = {"x": x, "y": y, "position": [x, y]}
        for key in ("width", "height", "colour", "shape", "label"):
            if key in attrs:
                node_attrs[key] = attrs[key]
        H.add_node(n, **node_attrs)

    for u, v, attrs in G.edges(data=True):
        bends = attrs.get("bends", [])
        x0, y0 = H.nodes[u]["x"], H.nodes[u]["y"]
        x1, y1 = H.nodes[v]["x"], H.nodes[v]["y"]

        if len(bends) < 2:
            path = f"M{x0},{y0} L{x1},{y1}"
        else:
            segs = [f"M{bends[0][0]},{bends[0][1]}"]
            segs += [f"L{bx},{by}" for bx, by in bends[1:]]
            path = " ".join(segs)

        edge_attrs = {"polyline": bool(attrs.get("polyline", False)), "path": path}
        for key in ("colour", "stroke_width", "label", "weight"):
            if key in attrs:
                edge_attrs[key] = attrs[key]
        H.add_edge(u, v, **edge_attrs)

    if output_file:
        write_geg(H, output_file)
    return H


def convert_gml_to_graphml(fname_gml: str, fname_graphml: str) -> None:
    """Convert GML → GraphML. Preserves node position, dimensions, colour,
    shape, label, and edge bends / styling via the GEG-canonical readers."""
    G = read_gml(fname_gml)
    write_graphml(G, fname_graphml)


def convert_graphml_to_gml(fname_graphml: str, fname_gml: str, with_nx: bool = False) -> None:
    """Convert GraphML → GML.

    Default path uses the GEG-canonical readers / writers and preserves
    node geometry, colour, shape, label, and edge bends / styling. Pass
    `with_nx=True` to fall back to `networkx.read_graphml` +
    `networkx.write_gml` for callers that want the raw networkx behaviour.
    """
    if with_nx:
        G = nx.read_graphml(fname_graphml)
        nx.write_gml(G, fname_gml)
    else:
        G = read_graphml(fname_graphml)
        write_gml(G, fname_gml)


# ---------- Generic dispatchers ----------

_READERS: Dict[str, Callable[[str], nx.Graph]] = {
    ".geg": read_geg,
    ".graphml": graphml_to_geg,
    ".gml": gml_to_geg,
}


def read_drawing(path: Any) -> nx.Graph:
    """Load a drawing from any supported format.

    Dispatches by file extension: `.geg` → `read_geg`, `.graphml` →
    `graphml_to_geg`, `.gml` → `gml_to_geg`. Returns a GEG-canonical
    NetworkX graph in every case (edges carry a `path` SVG string, nodes
    carry `x`, `y`, `position`).
    """
    ext = os.path.splitext(str(path))[1].lower()
    reader = _READERS.get(ext)
    if reader is None:
        raise ValueError(
            f"Unsupported input extension {ext!r} "
            f"(expected one of {sorted(_READERS)})"
        )
    return reader(str(path))


def write_drawing(G: nx.Graph, path: Any, **kwargs) -> None:
    """Write a drawing to any supported format.

    Dispatches by file extension: `.geg` → `write_geg`, `.graphml` →
    `write_graphml`, `.gml` → `write_gml`, `.svg` → `to_svg`. Extra
    keyword arguments are forwarded to the format-specific writer — for
    example `grid=True` or `scale=25.0` for `.svg`, `gml_format=True`
    for `.graphml`.
    """
    ext = os.path.splitext(str(path))[1].lower()
    if ext == ".geg":
        write_geg(G, str(path))
    elif ext == ".graphml":
        write_graphml(G, str(path), **kwargs)
    elif ext == ".gml":
        write_gml(G, str(path))
    elif ext == ".svg":
        # Lazy import: geg_parser pulls in scipy/svgpathtools and sits
        # higher in the dependency order (it imports from geg.io).
        from ..geg_parser import to_svg
        to_svg(G, str(path), **kwargs)
    else:
        raise ValueError(
            f"Unsupported output extension {ext!r} "
            "(expected one of '.geg', '.graphml', '.gml', '.svg')"
        )


def convert(src: Any, dst: Any, **kwargs) -> nx.Graph:
    """Load `src`, write to `dst`; formats detected from each extension.

    Returns the loaded graph so callers can inspect it. Extra kwargs are
    forwarded to `write_drawing`.

    Examples
    --------
    >>> convert("layout.gml", "layout.geg")          # GML → GEG
    >>> convert("layout.graphml", "layout.svg", grid=True)   # GraphML → SVG
    """
    G = read_drawing(src)
    write_drawing(G, dst, **kwargs)
    return G
