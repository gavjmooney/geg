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


# ---------- yEd corner-anchor auto-detect ----------

class TestYedCornerAnchor:
    """yEd stores node x/y as the top-left of the bounding box; every other
    source (GML export, our own writer) uses the centre. The reader
    auto-shifts when it detects a yEd-authored file via the `<!--Created
    by yEd-->` comment or the `xmlns:yed` namespace declaration.
    """

    def _yed_file(self, tmp_path, with_marker=True):
        """A minimal yEd-style GraphML file. `with_marker` controls whether
        the Created-by-yEd comment is present."""
        marker = "<!--Created by yEd 3.24-->" if with_marker else ""
        text = f"""<?xml version="1.0"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"
         xmlns:y="http://www.yworks.com/xml/graphml">
  {marker}
  <key id="d1" yfiles.type="nodegraphics" for="node"/>
  <graph id="G" edgedefault="undirected">
    <node id="a">
      <data key="d1">
        <y:ShapeNode>
          <y:Geometry x="100.0" y="50.0" width="40.0" height="30.0"/>
        </y:ShapeNode>
      </data>
    </node>
  </graph>
</graphml>
"""
        p = tmp_path / "f.graphml"
        p.write_text(text)
        return p

    def test_auto_detects_via_comment(self, tmp_path):
        p = self._yed_file(tmp_path, with_marker=True)
        G = read_graphml(str(p))
        # Top-left was (100, 50) with 40x30 node → centre (120, 65).
        assert G.nodes["a"]["x"] == 120.0
        assert G.nodes["a"]["y"] == 65.0

    def test_no_shift_when_file_is_not_yed(self, tmp_path):
        p = self._yed_file(tmp_path, with_marker=False)
        G = read_graphml(str(p))
        # No auto-detect trigger → x/y passed through.
        assert G.nodes["a"]["x"] == 100.0
        assert G.nodes["a"]["y"] == 50.0

    def test_explicit_true_forces_shift(self, tmp_path):
        p = self._yed_file(tmp_path, with_marker=False)
        G = read_graphml(str(p), yed_corner_anchor=True)
        assert G.nodes["a"]["x"] == 120.0
        assert G.nodes["a"]["y"] == 65.0

    def test_explicit_false_skips_shift(self, tmp_path):
        p = self._yed_file(tmp_path, with_marker=True)
        G = read_graphml(str(p), yed_corner_anchor=False)
        assert G.nodes["a"]["x"] == 100.0
        assert G.nodes["a"]["y"] == 50.0

    def test_graphml_to_geg_passes_kwarg_through(self, tmp_path):
        from geg import graphml_to_geg
        p = self._yed_file(tmp_path, with_marker=False)
        G = graphml_to_geg(str(p), yed_corner_anchor=True)
        assert G.nodes["a"]["x"] == 120.0

    def test_bends_line_up_with_shifted_centres(self, tmp_path):
        """End-to-end: a yEd file with an orthogonal L-bend must read back
        so that node centres and bend points form right-angle segments."""
        text = """<?xml version="1.0"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"
         xmlns:y="http://www.yworks.com/xml/graphml">
  <!--Created by yEd 3.24-->
  <key id="d1" yfiles.type="nodegraphics" for="node"/>
  <key id="d2" yfiles.type="edgegraphics" for="edge"/>
  <graph id="G" edgedefault="undirected">
    <node id="a">
      <data key="d1">
        <y:ShapeNode>
          <y:Geometry x="-15.0" y="-15.0" width="30.0" height="30.0"/>
        </y:ShapeNode>
      </data>
    </node>
    <node id="b">
      <data key="d1">
        <y:ShapeNode>
          <y:Geometry x="85.0" y="85.0" width="30.0" height="30.0"/>
        </y:ShapeNode>
      </data>
    </node>
    <edge source="a" target="b">
      <data key="d2">
        <y:PolyLineEdge>
          <y:Path><y:Point x="100.0" y="0.0"/></y:Path>
        </y:PolyLineEdge>
      </data>
    </edge>
  </graph>
</graphml>
"""
        p = tmp_path / "orth.graphml"
        p.write_text(text)
        G = read_graphml(str(p))
        # Centres: a=(0,0), b=(100,100), bend=(100,0) → right-angle L.
        assert G.nodes["a"]["x"] == 0.0 and G.nodes["a"]["y"] == 0.0
        assert G.nodes["b"]["x"] == 100.0 and G.nodes["b"]["y"] == 100.0
        assert G.edges["a", "b"]["bends"] == [(100.0, 0.0)]


class TestWriteGraphMLYedCornerAnchor:
    def test_default_write_round_trips_as_identity(self, tmp_path):
        """Without yed_corner_anchor the writer keeps centre-anchored coords
        and omits the yed namespace, so auto-detect does not fire on re-read."""
        G = read_graphml(str(SAMPLE))
        out = tmp_path / "rt.graphml"
        write_graphml(G, str(out))
        G2 = read_graphml(str(out))
        for n in G.nodes:
            assert G2.nodes[n]["x"] == G.nodes[n]["x"]
            assert G2.nodes[n]["y"] == G.nodes[n]["y"]

    def test_yed_corner_anchor_writer_emits_top_left_and_round_trips(self, tmp_path):
        """yed_corner_anchor=True shifts x/y to top-left on write AND declares
        xmlns:yed, so auto-detect fires on re-read and shifts back."""
        G = read_graphml(str(SAMPLE))  # centre-anchored
        out = tmp_path / "yed.graphml"
        write_graphml(G, str(out), yed_corner_anchor=True)
        # File should declare xmlns:yed.
        assert "xmlns:yed" in out.read_text()
        G2 = read_graphml(str(out))  # auto-detect → shift back
        for n in G.nodes:
            assert G2.nodes[n]["x"] == pytest.approx(G.nodes[n]["x"])
            assert G2.nodes[n]["y"] == pytest.approx(G.nodes[n]["y"])


YED_AUTHORED = Path(__file__).parent / "fixtures" / "io" / "yed_authored.graphml"


class TestYedAuthoredFixture:
    """End-to-end read / round-trip on a hand-written yEd-authored GraphML
    with 5 nodes, 4 square-cycle edges, one colour variant, and one edge
    with L-bend points. Pins behaviours that `TestYedCornerAnchor` only
    covers via inline XML strings."""

    def test_reads_node_centres_after_corner_shift(self):
        G = read_graphml(str(YED_AUTHORED))
        # yEd stores top-left; reader auto-detects (comment + xmlns:yed)
        # and shifts by (width/2, height/2) = (15, 15) for all 30x30 nodes.
        expected_centres = {
            "n0": (0.0, 0.0),
            "n1": (150.0, 0.0),
            "n2": (150.0, 150.0),
            "n3": (0.0, 150.0),
            "n4": (300.0, 75.0),
        }
        for n, (x, y) in expected_centres.items():
            assert G.nodes[n]["x"] == pytest.approx(x)
            assert G.nodes[n]["y"] == pytest.approx(y)

    def test_reads_bent_edge(self):
        G = read_graphml(str(YED_AUTHORED))
        # Edge n1-n4 has L-bend via (225, 0) and (225, 75).
        bends = G.edges["n1", "n4"]["bends"]
        assert bends == [(225.0, 0.0), (225.0, 75.0)]
        assert G.edges["n1", "n4"]["polyline"] is True

    def test_reads_node_and_edge_colours(self):
        G = read_graphml(str(YED_AUTHORED))
        assert G.nodes["n4"]["colour"] == "#CC99FF"
        assert G.nodes["n4"]["shape"] == "rectangle"
        assert G.edges["n1", "n4"]["colour"] == "#0000FF"

    def test_round_trip_preserves_centres_and_bends(self, tmp_path):
        """Read a yEd-authored file, write it back without the yed flag,
        and re-read: centres and bends must survive end-to-end."""
        G = read_graphml(str(YED_AUTHORED))
        out = tmp_path / "rt.graphml"
        write_graphml(G, str(out))
        G2 = read_graphml(str(out))
        for n in G.nodes:
            assert G2.nodes[n]["x"] == pytest.approx(G.nodes[n]["x"])
            assert G2.nodes[n]["y"] == pytest.approx(G.nodes[n]["y"])
        assert G2.edges["n1", "n4"]["bends"] == G.edges["n1", "n4"]["bends"]

    def test_graphml_to_geg_end_to_end(self, tmp_path):
        from geg import graphml_to_geg, read_geg
        out = tmp_path / "yed.geg"
        graphml_to_geg(str(YED_AUTHORED), str(out))
        G = read_geg(str(out))
        # Five nodes, five edges survived.
        assert G.number_of_nodes() == 5
        assert G.number_of_edges() == 5
        # L-bend encoded as M/L polyline in GEG path.
        path = G.edges["n1", "n4"]["path"]
        assert path.startswith("M150.0,0.0")
        assert "L225.0,0.0" in path
        assert "L225.0,75.0" in path
        assert path.rstrip().endswith("L300.0,75.0")


class TestWriteGraphMLMultigraph:
    def test_handles_multigraph(self, tmp_path):
        """write_graphml used to crash on MultiGraphs because the legacy
        loop did `G.edges[u, v]` after iterating `(u, v)` pairs, which
        fails on multigraphs (they require a key). Regression: both
        parallel edges must round-trip."""
        import networkx as nx
        G = nx.MultiGraph()
        G.add_node(0, x=0.0, y=0.0)
        G.add_node(1, x=100.0, y=0.0)
        G.add_edge(0, 1)
        G.add_edge(0, 1)  # parallel
        out = tmp_path / "mg.graphml"
        write_graphml(G, str(out))
        assert out.exists()
        # The XML should contain two <edge ... source="0" target="1"> entries.
        xml = out.read_text()
        assert xml.count('source="0"') == 2
