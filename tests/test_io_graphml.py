"""Tests for geg.io.graphml.

Covers the yEd-flavoured GraphML reader's attribute extraction, the
graphml_to_geg converter's attribute preservation, and the writer's round-
trip behaviour (read → write → read produces a graph with the same node/edge
attribute values).
"""

from pathlib import Path

import pytest

from geg import graphml_to_geg, read_geg
from geg.io.graphml import read_graphml, write_graphml


SAMPLE = Path(__file__).parent / "fixtures" / "io" / "sample.graphml"


# ---------- read_graphml ----------

class TestReadGraphML:
    def test_extracts_node_positions(self):
        G = read_graphml(str(SAMPLE))
        assert G.nodes["a"]["x"] == 0.0
        assert G.nodes["a"]["y"] == 0.0
        assert G.nodes["b"]["x"] == 100.0
        assert G.nodes["b"]["y"] == 50.0

    def test_extracts_node_dimensions(self):
        G = read_graphml(str(SAMPLE))
        assert G.nodes["a"]["width"] == 40.0
        assert G.nodes["a"]["height"] == 30.0
        assert G.nodes["b"]["width"] == 60.0
        assert G.nodes["b"]["height"] == 20.0

    def test_extracts_colour_on_node(self):
        G = read_graphml(str(SAMPLE))
        assert G.nodes["a"]["colour"] == "#FF0000"
        assert G.nodes["b"]["colour"] == "#00FF00"

    def test_extracts_shape(self):
        G = read_graphml(str(SAMPLE))
        assert G.nodes["a"]["shape"] == "ellipse"
        assert G.nodes["b"]["shape"] == "rectangle"

    def test_extracts_node_label(self):
        G = read_graphml(str(SAMPLE))
        assert G.nodes["a"]["label"] == "Alpha"
        assert G.nodes["b"]["label"] == "Beta"

    def test_extracts_edge_bends(self):
        G = read_graphml(str(SAMPLE))
        bends = G.edges["a", "b"]["bends"]
        assert bends == [(25.0, 25.0), (75.0, 25.0)]
        assert G.edges["a", "b"]["polyline"] is True

    def test_extracts_edge_styling(self):
        G = read_graphml(str(SAMPLE))
        assert G.edges["a", "b"]["colour"] == "#0000FF"
        assert G.edges["a", "b"]["stroke_width"] == 2.5

    def test_extracts_edge_label(self):
        G = read_graphml(str(SAMPLE))
        assert G.edges["a", "b"]["label"] == "bend-edge"

    def test_does_not_raise_on_missing_optional_attrs(self, tmp_path):
        """A node without Fill, Shape, or NodeLabel should still be readable."""
        minimal = tmp_path / "minimal.graphml"
        minimal.write_text("""<?xml version="1.0"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"
         xmlns:y="http://www.yworks.com/xml/graphml">
  <key id="d1" yfiles.type="nodegraphics" for="node"/>
  <key id="d2" yfiles.type="edgegraphics" for="edge"/>
  <graph id="G" edgedefault="undirected">
    <node id="only">
      <data key="d1">
        <y:ShapeNode>
          <y:Geometry x="0.0" y="0.0" width="30.0" height="30.0"/>
        </y:ShapeNode>
      </data>
    </node>
  </graph>
</graphml>
""")
        G = read_graphml(str(minimal))
        assert G.nodes["only"]["x"] == 0.0
        # Optional attrs simply absent, not crash.
        assert "colour" not in G.nodes["only"]
        assert "shape" not in G.nodes["only"]


# ---------- graphml_to_geg ----------

class TestGraphMLToGeg:
    def test_preserves_node_positions(self):
        G = graphml_to_geg(str(SAMPLE))
        assert G.nodes["a"]["x"] == 0.0
        assert G.nodes["a"]["position"] == [0.0, 0.0]
        assert G.nodes["b"]["x"] == 100.0

    def test_preserves_node_attrs(self):
        G = graphml_to_geg(str(SAMPLE))
        assert G.nodes["a"]["colour"] == "#FF0000"
        assert G.nodes["a"]["shape"] == "ellipse"
        assert G.nodes["a"]["label"] == "Alpha"
        assert G.nodes["a"]["width"] == 40.0
        assert G.nodes["a"]["height"] == 30.0

    def test_preserves_edge_attrs(self):
        G = graphml_to_geg(str(SAMPLE))
        edge = G.edges["a", "b"]
        assert edge["polyline"] is True
        assert edge["colour"] == "#0000FF"
        assert edge["stroke_width"] == 2.5
        assert edge["label"] == "bend-edge"

    def test_encodes_bends_as_svg_path(self):
        G = graphml_to_geg(str(SAMPLE))
        path = G.edges["a", "b"]["path"]
        # Source → first bend → second bend → target.
        assert path.startswith("M0.0,0.0")
        assert "L25.0,25.0" in path
        assert "L75.0,25.0" in path
        assert path.rstrip().endswith("L100.0,50.0")

    def test_optional_geg_writeout(self, tmp_path):
        out = tmp_path / "from_graphml.geg"
        G = graphml_to_geg(str(SAMPLE), str(out))
        # The written GEG file must be loadable and preserve the attrs.
        G2 = read_geg(str(out))
        assert G2.nodes["a"]["label"] == "Alpha"
        assert G2.edges["a", "b"]["colour"] == "#0000FF"


# ---------- write_graphml + read_graphml round trip ----------

class TestGraphMLWriteRoundTrip:
    def test_write_then_read_preserves_basic_attrs(self, tmp_path):
        G = read_graphml(str(SAMPLE))
        out = tmp_path / "roundtrip.graphml"
        write_graphml(G, str(out))
        G2 = read_graphml(str(out))

        for n in G.nodes:
            assert G2.nodes[n]["x"] == G.nodes[n]["x"]
            assert G2.nodes[n]["y"] == G.nodes[n]["y"]
            assert G2.nodes[n].get("colour") == G.nodes[n].get("colour")
            assert G2.nodes[n].get("shape") == G.nodes[n].get("shape")
            assert G2.nodes[n].get("label") == G.nodes[n].get("label")
            assert G2.nodes[n].get("width") == G.nodes[n].get("width")
            assert G2.nodes[n].get("height") == G.nodes[n].get("height")

        for u, v in G.edges:
            assert G2.edges[u, v].get("bends") == G.edges[u, v].get("bends")
            assert G2.edges[u, v].get("colour") == G.edges[u, v].get("colour")
            assert G2.edges[u, v].get("stroke_width") == G.edges[u, v].get("stroke_width")
