"""GML (yEd-flavoured) reader, writer, and GML → GEG converter.

GML (Graph Modelling Language) is parsed via `networkx.read_gml`. yEd and
other tools store drawing attributes under a `graphics` dict per node/edge;
this module unpacks the common fields into GEG-canonical attribute names
(`x`, `y`, `width`, `height`, `colour`, `shape`, `label`, `bends`, …) so
that callers get a similarly-shaped graph from `read_gml` as from
`read_graphml`.
"""

from typing import Optional

import networkx as nx

from .geg import write_geg


# ---------- read ----------

def _extract_node_attrs(src_attrs: dict) -> dict:
    """Map a GML node's attributes onto GEG-canonical ones."""
    g = src_attrs.get("graphics", {}) or {}
    try:
        x = float(g.get("x", 0))
        y = float(g.get("y", 0))
    except (TypeError, ValueError):
        x, y = 0.0, 0.0
    out = {"x": x, "y": y}

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

    if "label" in src_attrs:
        out["label"] = src_attrs["label"]
    return out


def _extract_edge_attrs(src_attrs: dict) -> dict:
    """Map a GML edge's attributes onto GEG-canonical ones.

    Returns a dict with `bends` (list of (x, y) tuples, possibly empty),
    `polyline` (bool), and any styling / label / weight found. yEd GML
    typically lists *all* polyline vertices in `Line` including the source
    and target endpoints, so `bends` is preserved verbatim from the file.
    """
    g = src_attrs.get("graphics", {}) or {}
    raw_points = g.get("Line", {}).get("point", []) if isinstance(g, dict) else []

    bends: list = []
    prev = None
    for p in raw_points:
        try:
            current = (float(p["x"]), float(p["y"]))
        except (TypeError, ValueError, KeyError):
            continue
        if current != prev:
            bends.append(current)
        prev = current

    out: dict = {
        "polyline": bool(g.get("smoothBends", 0)) or len(bends) > 2,
        "bends": bends,
    }

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


def read_gml(input_file: str) -> nx.Graph:
    """Read a yEd-flavoured GML drawing into a NetworkX graph.

    Extracts per-node geometry (`x`, `y`, `width`, `height`), fill colour,
    shape, and label (when present). Extracts per-edge polyline bends,
    line-style colour / width, label, and weight. Missing optional
    attributes default to absent rather than raising.

    The returned graph's edge geometry is exposed as a `bends` list plus a
    `polyline` flag, not as an SVG `path` string — use `gml_to_geg` if you
    need GEG-canonical path encoding.
    """
    G = nx.read_gml(input_file, label=None)

    if G.is_multigraph():
        H: nx.Graph = nx.MultiDiGraph() if G.is_directed() else nx.MultiGraph()
    else:
        H = nx.DiGraph() if G.is_directed() else nx.Graph()
    H.graph.update(G.graph)

    for n, attrs in G.nodes(data=True):
        H.add_node(n, **_extract_node_attrs(attrs))

    for u, v, attrs in G.edges(data=True):
        H.add_edge(u, v, **_extract_edge_attrs(attrs))

    return H


# ---------- write ----------

def _format_number(value) -> str:
    try:
        return f"{float(value)}"
    except (TypeError, ValueError):
        return "0.0"


def write_gml(G: nx.Graph, output_file: str) -> None:
    """Write a NetworkX graph to a yEd-flavoured GML file.

    Node attributes honoured on output: `x`/`y` (default 0), `width`/`height`
    (default 30), `shape` (default "ellipse"), `colour`/`color` (default
    "#FFCC00"), `label` (optional). Edge attributes honoured: `bends` (list
    of (x, y) tuples or dicts with `x`/`y`), `colour`/`color` (default
    "#000000"), `stroke_width` (default 1.0), `label`, `weight`.
    """
    directed = 1 if isinstance(G, (nx.DiGraph, nx.MultiDiGraph)) else 0
    lines: list = ["graph [", f"  directed {directed}"]

    for n, attrs in G.nodes(data=True):
        x = _format_number(attrs.get("x", 0.0))
        y = _format_number(attrs.get("y", 0.0))
        w = _format_number(attrs.get("width", 30.0))
        h = _format_number(attrs.get("height", 30.0))
        shape = str(attrs.get("shape", "ellipse"))
        colour = str(attrs.get("colour", attrs.get("color", "#FFCC00")))
        label = attrs.get("label")

        lines.append("  node [")
        lines.append(f"    id {n}")
        if label:
            lines.append(f'    label "{label}"')
        lines.append("    graphics [")
        lines.append(f"      x {x}")
        lines.append(f"      y {y}")
        lines.append(f"      w {w}")
        lines.append(f"      h {h}")
        lines.append(f'      type "{shape}"')
        lines.append(f'      fill "{colour}"')
        lines.append("    ]")
        lines.append("  ]")

    for u, v, attrs in G.edges(data=True):
        label = attrs.get("label")
        weight = attrs.get("weight")
        colour = str(attrs.get("colour", attrs.get("color", "#000000")))
        width = _format_number(attrs.get("stroke_width", 1.0))

        bends_raw = attrs.get("bends") or []
        bends: list = []
        for b in bends_raw:
            if isinstance(b, dict) and "x" in b and "y" in b:
                bends.append((b["x"], b["y"]))
            else:
                try:
                    bx, by = b
                    bends.append((bx, by))
                except (TypeError, ValueError):
                    continue

        lines.append("  edge [")
        lines.append(f"    source {u}")
        lines.append(f"    target {v}")
        if label:
            lines.append(f'    label "{label}"')
        if weight is not None:
            lines.append(f"    weight {_format_number(weight)}")
        lines.append("    graphics [")
        lines.append(f'      fill "{colour}"')
        lines.append(f"      width {width}")
        lines.append(f"      smoothBends {1 if attrs.get('polyline') and bends else 0}")
        if bends:
            lines.append("      Line [")
            for bx, by in bends:
                lines.append(
                    f"        point [ x {_format_number(bx)} y {_format_number(by)} ]"
                )
            lines.append("      ]")
        lines.append("    ]")
        lines.append("  ]")

    lines.append("]")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ---------- convert ----------

def gml_to_geg(input_file: str, output_file: Optional[str] = None) -> nx.Graph:
    """Convert a yEd GML drawing to a GEG NetworkX graph.

    Reads via `read_gml`, then rewrites edge bends as SVG `M…L…` paths and
    adds a `position` list per node (GEG-canonical form). Optionally writes
    the result to `output_file` as GEG JSON.
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
