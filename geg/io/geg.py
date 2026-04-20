"""GEG (JSON) file format: reader, writer, and file-level introspection."""

import json
from typing import Any

import networkx as nx


def _coerce_bool(value: Any) -> Any:
    """Convert common string/number representations to Python bool.

    Returns the original value if it cannot be confidently coerced.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"true", "1", "yes", "y", "t"}:
            return True
        if v in {"false", "0", "no", "n", "f"}:
            return False
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return value


def has_self_loops_file(input_file: str) -> bool:
    """Return True iff the GEG file contains any self-loop (source == target)."""
    with open(input_file, "r") as f:
        data = json.load(f)
    for edge in data.get("edges", []):
        if edge["source"] == edge["target"]:
            return True
    return False


def is_multigraph_file(input_file: str) -> bool:
    """Return True iff the GEG file has more than one edge between the same
    pair (normalised as unordered for undirected graphs)."""
    with open(input_file, "r") as f:
        data = json.load(f)
    directed = _coerce_bool(data.get("graph", {}).get("directed", False))
    seen: dict = {}
    for edge in data.get("edges", []):
        src = edge["source"]
        tgt = edge["target"]
        key = (src, tgt) if directed else tuple(sorted((src, tgt)))
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            return True
    return False


def _extract_xy(attrs: dict) -> tuple:
    """Resolve (x, y) from an attr dict, trying 'x'/'y', 'pos', 'position' in order.

    Returns (x, y) as floats, or (None, None) if coordinates can't be parsed.
    """
    # Case 1: explicit x/y.
    if "x" in attrs and "y" in attrs:
        try:
            return float(attrs["x"]), float(attrs["y"])
        except (TypeError, ValueError):
            pass

    # Case 2: 'pos'.
    pos = attrs.get("pos")
    if pos is not None:
        try:
            if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                return float(pos[0]), float(pos[1])
            if isinstance(pos, dict) and "x" in pos and "y" in pos:
                return float(pos["x"]), float(pos["y"])
        except (TypeError, ValueError):
            pass

    # Case 3: 'position'.
    position = attrs.get("position")
    if position is not None:
        try:
            if isinstance(position, (list, tuple)) and len(position) >= 2:
                return float(position[0]), float(position[1])
            if isinstance(position, dict) and "x" in position and "y" in position:
                return float(position["x"]), float(position["y"])
        except (TypeError, ValueError):
            pass

    return None, None


def read_geg(input_file: str) -> nx.Graph:
    """Read a GEG file into a NetworkX graph, preserving attributes.

    Accepts node coordinates as `x`/`y`, `pos`, or `position` (list, tuple, or
    dict) and normalises every node to have all three of `x`, `y`, and
    `position`. Graph-level metadata is copied onto `G.graph`.

    Returns a Graph / DiGraph / MultiGraph / MultiDiGraph matching the file's
    `directed` flag and whether any pair of endpoints has multiple edges.
    """
    with open(input_file, "r") as f:
        data = json.load(f)

    directed = _coerce_bool(data.get("graph", {}).get("directed", False))
    if is_multigraph_file(input_file):
        G = nx.MultiDiGraph() if directed else nx.MultiGraph()
    else:
        G = nx.DiGraph() if directed else nx.Graph()

    G.graph.update({k: v for k, v in data.get("graph", {}).items() if k != "directed"})

    for node in data.get("nodes", []):
        node_id = node["id"]
        attrs = {k: v for k, v in node.items() if k != "id"}
        x, y = _extract_xy(attrs)
        if x is not None and y is not None:
            attrs["x"] = x
            attrs["y"] = y
            attrs["position"] = [x, y]
        G.add_node(node_id, **attrs)

    for edge in data.get("edges", []):
        source = edge["source"]
        target = edge["target"]
        # source and target are structural (index into the edge tuple), not attrs.
        edge_attrs = {k: v for k, v in edge.items() if k not in ("source", "target")}
        if "polyline" in edge_attrs:
            edge_attrs["polyline"] = _coerce_bool(edge_attrs["polyline"])
        G.add_edge(source, target, **edge_attrs)

    return G


def write_geg(G: nx.Graph, output_file: str) -> None:
    """Write a NetworkX graph to the GEG JSON format.

    Every node gets a `position` array (derived from `x`/`y` or a `pos`
    attribute if necessary). Every edge gets an `id` (derived from
    `source-target` if the graph doesn't already have one).
    """
    data = {
        "graph": {
            "directed": isinstance(G, (nx.DiGraph, nx.MultiDiGraph)),
            **G.graph,
        },
        "nodes": [],
        "edges": [],
    }

    for node, attrs in G.nodes(data=True):
        node_data = {"id": node, **attrs}
        if "position" not in node_data:
            x = node_data.get("x")
            y = node_data.get("y")
            if x is None or y is None:
                pos = node_data.get("pos")
                if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                    x, y = pos[0], pos[1]
                elif isinstance(pos, dict) and "x" in pos and "y" in pos:
                    x, y = pos["x"], pos["y"]
            if x is not None and y is not None:
                try:
                    node_data["position"] = [float(x), float(y)]
                except (TypeError, ValueError):
                    pass
        data["nodes"].append(node_data)

    for source, target, attrs in G.edges(data=True):
        edge_data = {
            "id": attrs.get("id", f"{source}-{target}"),
            "source": source,
            "target": target,
        }
        edge_data.update({k: v for k, v in attrs.items() if k != "id"})
        data["edges"].append(edge_data)

    with open(output_file, "w") as f:
        json.dump(data, f, indent=4)
