"""GraphML (yEd-flavoured) reader, writer, and GraphML → GEG converter."""

import xml.etree.ElementTree as ET
from typing import Optional
from xml.dom import minidom

import networkx as nx

from .geg import write_geg

GRAPHML_NS = "http://graphml.graphdrawing.org/xmlns"
YED_NS = "http://www.yworks.com/xml/graphml"


def _find_yfiles_keys(root):
    """Locate the data-key ids used for node graphics and edge graphics."""
    node_key = "d1"
    edge_key = "d2"
    for data_elm in root:
        if data_elm.get("yfiles.type") == "nodegraphics":
            node_key = data_elm.get("id")
        elif data_elm.get("yfiles.type") == "edgegraphics":
            edge_key = data_elm.get("id")
    return node_key, edge_key


def read_graphml(filename: str) -> nx.Graph:
    """Read a yEd-flavoured GraphML drawing into a NetworkX graph.

    Extracts per-node geometry (x, y, width, height), fill colour, shape, and
    label (when present). Extracts per-edge polyline bends, line-style colour
    and width, and label. Missing optional attributes default sensibly rather
    than raising.
    """
    tree = ET.parse(filename)
    root = tree.getroot()

    node_key, edge_key = _find_yfiles_keys(root)

    # Detect directedness from <graph edgedefault="...">.
    graph_elm = root.find(f"{{{GRAPHML_NS}}}graph")
    directed = graph_elm is not None and graph_elm.get("edgedefault") == "directed"
    G = nx.DiGraph() if directed else nx.Graph()

    for node in root.findall(f".//{{{GRAPHML_NS}}}node"):
        attrs: dict = {}
        for data in node:
            if data.get("key") != node_key:
                continue
            for shape_node in data:
                for elm in shape_node:
                    tag = elm.tag
                    if tag == f"{{{YED_NS}}}Geometry":
                        try:
                            attrs["x"] = float(elm.get("x", 0))
                            attrs["y"] = float(elm.get("y", 0))
                        except (TypeError, ValueError):
                            pass
                        if elm.get("width") is not None:
                            try:
                                attrs["width"] = float(elm.get("width"))
                            except (TypeError, ValueError):
                                pass
                        if elm.get("height") is not None:
                            try:
                                attrs["height"] = float(elm.get("height"))
                            except (TypeError, ValueError):
                                pass
                    elif tag == f"{{{YED_NS}}}Fill":
                        if elm.get("color"):
                            attrs["colour"] = elm.get("color")
                    elif tag == f"{{{YED_NS}}}Shape":
                        if elm.get("type"):
                            attrs["shape"] = elm.get("type")
                    elif tag == f"{{{YED_NS}}}NodeLabel":
                        if elm.text and elm.text.strip():
                            attrs["label"] = elm.text.strip()
        G.add_node(node.get("id"), **attrs)

    for edge in root.findall(f".//{{{GRAPHML_NS}}}edge"):
        source = edge.get("source")
        target = edge.get("target")
        bends = []
        edge_attrs: dict = {}
        for data in edge:
            if data.get("key") != edge_key:
                continue
            for poly_edge in data:
                for child in poly_edge:
                    tag = child.tag
                    if tag == f"{{{YED_NS}}}Path":
                        for point in child.findall(f"{{{YED_NS}}}Point"):
                            try:
                                bends.append((float(point.get("x")), float(point.get("y"))))
                            except (TypeError, ValueError):
                                pass
                    elif tag == f"{{{YED_NS}}}LineStyle":
                        if child.get("color"):
                            edge_attrs["colour"] = child.get("color")
                        if child.get("width"):
                            try:
                                edge_attrs["stroke_width"] = float(child.get("width"))
                            except (TypeError, ValueError):
                                pass
                    elif tag == f"{{{YED_NS}}}EdgeLabel":
                        if child.text and child.text.strip():
                            edge_attrs["label"] = child.text.strip()

        edge_attrs["polyline"] = len(bends) > 0
        edge_attrs["bends"] = bends
        G.add_edge(source, target, **edge_attrs)

    return G


def write_graphml(G: nx.Graph, filename: str, gml_format: bool = False) -> None:
    """Write a NetworkX graph to a yEd-flavoured GraphML file.

    Node attributes recognised on output: `shape` (defaults to "ellipse"),
    `label` (defaults to empty), `colour`/`color` (defaults to "#FFCC00"),
    `width`/`height` (defaults to 30), `x`/`y` (via `graphics` dict if
    `gml_format=True`, else directly). Edge bends use the `bends` attribute.
    """
    doc = minidom.Document()
    root = doc.createElement("graphml")
    root.setAttribute("xmlns", GRAPHML_NS)
    root.setAttribute("xmlns:y", YED_NS)
    root.setAttribute("xmlns:yed", "http://www.yworks.com/xml/yed/3")
    doc.appendChild(root)

    for key_id, yfiles_type, scope in [
        ("d1", "nodegraphics", "node"),
        ("d2", "edgegraphics", "edge"),
    ]:
        key = doc.createElement("key")
        key.setAttribute("id", key_id)
        key.setAttribute("yfiles.type", yfiles_type)
        key.setAttribute("for", scope)
        root.appendChild(key)

    graph_node = doc.createElement("graph")
    graph_node.setAttribute("id", "G")
    graph_node.setAttribute(
        "edgedefault",
        "directed" if isinstance(G, (nx.DiGraph, nx.MultiDiGraph)) else "undirected",
    )
    root.appendChild(graph_node)

    for n in G.nodes():
        attrs = G.nodes[n]
        node = doc.createElement("node")
        node.setAttribute("id", f"n{n}" if gml_format else str(n))
        data = doc.createElement("data")
        data.setAttribute("key", "d1")

        shape_element = doc.createElement("y:ShapeNode")

        fill = doc.createElement("y:Fill")
        fill.setAttribute("transparent", "false")
        fill.setAttribute(
            "color",
            str(attrs.get("colour", attrs.get("color", "#FFCC00"))),
        )
        shape_element.appendChild(fill)

        geometry = doc.createElement("y:Geometry")
        geometry.setAttribute("height", str(attrs.get("height", 30.0)))
        geometry.setAttribute("width", str(attrs.get("width", 30.0)))
        if gml_format:
            gx = float(attrs.get("graphics", {}).get("x", 0)) - 15
            gy = float(attrs.get("graphics", {}).get("y", 0)) - 15
            geometry.setAttribute("x", str(gx))
            geometry.setAttribute("y", str(gy))
        else:
            geometry.setAttribute("x", str(attrs.get("x", 0)))
            geometry.setAttribute("y", str(attrs.get("y", 0)))
        shape_element.appendChild(geometry)

        shape_node = doc.createElement("y:Shape")
        shape_node.setAttribute("type", attrs.get("shape", "ellipse"))
        shape_element.appendChild(shape_node)

        label = doc.createElement("y:NodeLabel")
        label.setAttribute("textColor", "#000000")
        label.setAttribute("fontSize", "6")
        label.appendChild(doc.createTextNode(str(attrs.get("label", "\n"))))
        shape_element.appendChild(label)

        data.appendChild(shape_element)
        node.appendChild(data)
        graph_node.appendChild(node)

    for u, v in G.edges():
        attrs = G.edges[u, v]
        edge = doc.createElement("edge")
        edge.setAttribute("source", f"n{u}" if gml_format else str(u))
        edge.setAttribute("target", f"n{v}" if gml_format else str(v))
        graph_node.appendChild(edge)

        data = doc.createElement("data")
        data.setAttribute("key", "d2")
        edge.appendChild(data)

        poly_edge = doc.createElement("y:PolyLineEdge")
        data.appendChild(poly_edge)

        path = doc.createElement("y:Path")
        path.setAttribute("sx", "0.0")
        path.setAttribute("sy", "0.0")
        path.setAttribute("tx", "0.0")
        path.setAttribute("ty", "0.0")
        poly_edge.appendChild(path)

        bends = []
        if gml_format:
            bends = [
                (bend["x"], bend["y"])
                for bend in attrs.get("graphics", {}).get("Line", {}).get("point", [])
            ]
        elif "bends" in attrs:
            bends = [(bx, by) for bx, by in attrs["bends"]]
        for bx, by in bends:
            point = doc.createElement("y:Point")
            point.setAttribute("x", str(bx))
            point.setAttribute("y", str(by))
            path.appendChild(point)

        linestyle = doc.createElement("y:LineStyle")
        linestyle.setAttribute("color", str(attrs.get("colour", attrs.get("color", "#000000"))))
        linestyle.setAttribute("type", "line")
        linestyle.setAttribute("width", str(attrs.get("stroke_width", 1.0)))
        poly_edge.appendChild(linestyle)

        arrows = doc.createElement("y:Arrows")
        arrows.setAttribute("source", "none")
        arrows.setAttribute("target", "none")
        poly_edge.appendChild(arrows)

        bendstyle = doc.createElement("y:BendStyle")
        bendstyle.setAttribute("smoothed", "true")
        poly_edge.appendChild(bendstyle)

    with open(filename, "w") as f:
        f.write(doc.toprettyxml(indent="    "))


def graphml_to_geg(input_file: str, output_file: Optional[str] = None) -> nx.Graph:
    """Convert a yEd GraphML drawing to a GEG NetworkX graph.

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
        node_attrs = {
            "x": x,
            "y": y,
            "position": [x, y],
        }
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


def convert_gml_to_graphml(fname_gml: str, fname_graphml: str) -> None:
    G = nx.read_gml(fname_gml, label=None)
    write_graphml(G, fname_graphml, gml_format=True)


def convert_graphml_to_gml(fname_graphml: str, fname_gml: str, with_nx: bool = False) -> None:
    """Convert GraphML → GML via networkx. Does NOT preserve node positions
    or edge attributes; use only on graphs, not drawings."""
    if with_nx:
        G = nx.read_graphml(fname_graphml)
    else:
        G = read_graphml(fname_graphml)
    nx.write_gml(G, fname_gml)
