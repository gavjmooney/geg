"""GraphML (yEd-flavoured) reader and writer.

Format-to-format conversion (including `graphml_to_geg`,
`convert_gml_to_graphml`, `convert_graphml_to_gml`) lives in
`geg.io.convert`.
"""

import xml.etree.ElementTree as ET
from typing import Optional
from xml.dom import minidom

import networkx as nx

GRAPHML_NS = "http://graphml.graphdrawing.org/xmlns"
YED_NS = "http://www.yworks.com/xml/graphml"


def _file_is_yed_authored(filename: str) -> bool:
    """Detect whether a GraphML file was emitted by yEd.

    yEd writes a `<!--Created by yEd ...-->` comment and declares the
    `xmlns:yed="http://www.yworks.com/xml/yed/3"` namespace on the root.
    Either marker is sufficient; we scan the prologue so we don't pay for
    parsing the whole file a second time.
    """
    try:
        with open(filename, "r", encoding="utf-8") as f:
            for _ in range(40):
                line = f.readline()
                if not line:
                    break
                if "xmlns:yed=" in line or "Created by yEd" in line:
                    return True
    except OSError:
        pass
    return False


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


def read_graphml(
    filename: str,
    yed_corner_anchor: Optional[bool] = None,
) -> nx.Graph:
    """Read a yEd-flavoured GraphML drawing into a NetworkX graph.

    Extracts per-node geometry (x, y, width, height), fill colour, shape, and
    label (when present). Extracts per-edge polyline bends, line-style colour
    and width, and label. Missing optional attributes default sensibly rather
    than raising.

    yEd-origin quirk
    ----------------
    yEd stores node `x`/`y` as the *top-left corner* of the node's bounding
    box. Every other source — including our own `write_gml`, the `.gml` side
    of yEd's own export, and hand-written GraphML — treats `x`/`y` as the
    *centre*. Edge bends are always in absolute drawing coordinates, so if
    the top-left convention is kept, bend points land in the wrong place
    relative to the node and orthogonal L-shaped routings come out diagonal.

    `yed_corner_anchor` controls whether to shift x,y by (width/2, height/2)
    after reading:

        - `None` (default): auto-detect from the file's prologue (presence
          of the `xmlns:yed` namespace or a `<!--Created by yEd-->` comment).
        - `True`:  always shift — force yEd-style interpretation.
        - `False`: never shift — treat x,y as centre (our hand-written /
          non-yEd convention).
    """
    tree = ET.parse(filename)
    root = tree.getroot()

    if yed_corner_anchor is None:
        yed_corner_anchor = _file_is_yed_authored(filename)

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
        if yed_corner_anchor and "x" in attrs and "y" in attrs:
            # yEd stores (x, y) as the top-left corner of the bounding box;
            # shift to the node centre so bends (which are in absolute
            # drawing coordinates) line up correctly.
            if "width" in attrs:
                attrs["x"] += attrs["width"] / 2.0
            if "height" in attrs:
                attrs["y"] += attrs["height"] / 2.0
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


def write_graphml(
    G: nx.Graph,
    filename: str,
    gml_format: bool = False,
    yed_corner_anchor: bool = False,
) -> None:
    """Write a NetworkX graph to a yEd-flavoured GraphML file.

    Node attributes recognised on output: `shape` (defaults to "ellipse"),
    `label` (defaults to empty), `colour`/`color` (defaults to "#FFCC00"),
    `width`/`height` (defaults to 30), `x`/`y` (via `graphics` dict if
    `gml_format=True`, else directly). Edge bends use the `bends` attribute.

    Set `yed_corner_anchor=True` to emit a file that matches yEd's own
    convention — `x`/`y` shifted to the top-left corner of each node's
    bounding box — and to declare the `yed` namespace so our reader's
    auto-detect picks it up. The default keeps centre-anchored coordinates
    and omits the yed namespace, which makes library round-trips (write →
    read) an identity.
    """
    doc = minidom.Document()
    root = doc.createElement("graphml")
    root.setAttribute("xmlns", GRAPHML_NS)
    root.setAttribute("xmlns:y", YED_NS)
    if yed_corner_anchor:
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

        w = float(attrs.get("width", 30.0))
        h = float(attrs.get("height", 30.0))
        geometry = doc.createElement("y:Geometry")
        geometry.setAttribute("height", str(h))
        geometry.setAttribute("width", str(w))
        if gml_format:
            gx = float(attrs.get("graphics", {}).get("x", 0)) - 15
            gy = float(attrs.get("graphics", {}).get("y", 0)) - 15
            geometry.setAttribute("x", str(gx))
            geometry.setAttribute("y", str(gy))
        else:
            x = float(attrs.get("x", 0))
            y = float(attrs.get("y", 0))
            if yed_corner_anchor:
                x -= w / 2.0
                y -= h / 2.0
            geometry.setAttribute("x", str(x))
            geometry.setAttribute("y", str(y))
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

    # `data=True` yields (u, v, attrs) on simple graphs and (u, v, attrs)
    # on multigraphs too (with parallel edges appearing separately); avoids
    # the `G.edges[u, v]` subscript that fails on MultiGraphs.
    for u, v, attrs in G.edges(data=True):
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


