"""Tests for geg.io.gml — read_gml, write_gml, and the gml_to_geg converter."""

from pathlib import Path

import pytest

from geg import gml_to_geg, read_geg, read_gml, write_gml


SAMPLE = Path(__file__).parent / "fixtures" / "io" / "sample.gml"


class TestGMLToGeg:
    def test_preserves_node_positions(self):
        G = gml_to_geg(str(SAMPLE))
        # Nodes are id'd 0 and 1 in the sample.
        assert G.nodes[0]["x"] == 0.0
        assert G.nodes[0]["y"] == 0.0
        assert G.nodes[0]["position"] == [0.0, 0.0]
        assert G.nodes[1]["x"] == 100.0
        assert G.nodes[1]["y"] == 50.0

    def test_preserves_node_dimensions(self):
        G = gml_to_geg(str(SAMPLE))
        assert G.nodes[0]["width"] == 40.0
        assert G.nodes[0]["height"] == 30.0
        assert G.nodes[1]["width"] == 60.0
        assert G.nodes[1]["height"] == 20.0

    def test_preserves_node_colour_and_shape(self):
        G = gml_to_geg(str(SAMPLE))
        assert G.nodes[0]["colour"] == "#FF0000"
        assert G.nodes[0]["shape"] == "ellipse"
        assert G.nodes[1]["colour"] == "#00FF00"
        assert G.nodes[1]["shape"] == "rectangle"

    def test_preserves_node_label(self):
        G = gml_to_geg(str(SAMPLE))
        assert G.nodes[0]["label"] == "Alpha"
        assert G.nodes[1]["label"] == "Beta"

    def test_preserves_edge_weight(self):
        G = gml_to_geg(str(SAMPLE))
        assert G.edges[0, 1]["weight"] == 2.5

    def test_preserves_edge_colour_and_stroke_width(self):
        G = gml_to_geg(str(SAMPLE))
        assert G.edges[0, 1]["colour"] == "#0000FF"
        assert G.edges[0, 1]["stroke_width"] == 2.5

    def test_preserves_edge_label(self):
        G = gml_to_geg(str(SAMPLE))
        assert G.edges[0, 1]["label"] == "bend-edge"

    def test_encodes_edge_path_from_bends(self):
        G = gml_to_geg(str(SAMPLE))
        path = G.edges[0, 1]["path"]
        # Four points in the Line: (0,0), (25,25), (75,25), (100,50).
        assert path.startswith("M0.0,0.0")
        assert "L25.0,25.0" in path
        assert "L75.0,25.0" in path
        assert path.rstrip().endswith("L100.0,50.0")

    def test_polyline_flag_set_for_bent_edges(self):
        G = gml_to_geg(str(SAMPLE))
        assert G.edges[0, 1]["polyline"] is True

    def test_optional_geg_writeout(self, tmp_path):
        out = tmp_path / "from_gml.geg"
        G = gml_to_geg(str(SAMPLE), str(out))
        G2 = read_geg(str(out))
        # Round-trip: every attribute we extracted should still be present.
        assert G2.nodes[0]["label"] == "Alpha"
        assert G2.nodes[0]["colour"] == "#FF0000"
        assert G2.nodes[0]["width"] == 40.0
        assert G2.edges[0, 1]["weight"] == 2.5
        assert G2.edges[0, 1]["colour"] == "#0000FF"
        assert G2.edges[0, 1]["label"] == "bend-edge"


class TestMinimalGML:
    def test_straight_edge_no_graphics(self, tmp_path):
        """A minimal GML with just positions and a plain edge — no bends, no
        styling — should still produce a usable GEG with a straight path."""
        gml = tmp_path / "min.gml"
        gml.write_text("""graph [
  directed 0
  node [ id 0 graphics [ x 0.0 y 0.0 ] ]
  node [ id 1 graphics [ x 1.0 y 0.0 ] ]
  edge [ source 0 target 1 ]
]
""")
        G = gml_to_geg(str(gml))
        assert G.number_of_edges() == 1
        edge = G.edges[0, 1]
        assert edge["polyline"] is False
        assert edge["path"] == "M0.0,0.0 L1.0,0.0"


# ---------- read_gml ----------

class TestReadGML:
    def test_extracts_node_positions(self):
        G = read_gml(str(SAMPLE))
        assert G.nodes[0]["x"] == 0.0
        assert G.nodes[0]["y"] == 0.0
        assert G.nodes[1]["x"] == 100.0
        assert G.nodes[1]["y"] == 50.0

    def test_extracts_node_dimensions(self):
        G = read_gml(str(SAMPLE))
        assert G.nodes[0]["width"] == 40.0
        assert G.nodes[0]["height"] == 30.0
        assert G.nodes[1]["width"] == 60.0
        assert G.nodes[1]["height"] == 20.0

    def test_extracts_node_colour_shape_label(self):
        G = read_gml(str(SAMPLE))
        assert G.nodes[0]["colour"] == "#FF0000"
        assert G.nodes[0]["shape"] == "ellipse"
        assert G.nodes[0]["label"] == "Alpha"
        assert G.nodes[1]["shape"] == "rectangle"

    def test_extracts_edge_bends_and_polyline(self):
        G = read_gml(str(SAMPLE))
        # yEd GML lists every point including endpoints in `Line`.
        assert G.edges[0, 1]["bends"] == [
            (0.0, 0.0), (25.0, 25.0), (75.0, 25.0), (100.0, 50.0),
        ]
        assert G.edges[0, 1]["polyline"] is True

    def test_extracts_edge_styling(self):
        G = read_gml(str(SAMPLE))
        assert G.edges[0, 1]["colour"] == "#0000FF"
        assert G.edges[0, 1]["stroke_width"] == 2.5
        assert G.edges[0, 1]["label"] == "bend-edge"
        assert G.edges[0, 1]["weight"] == 2.5

    def test_does_not_set_path_attr(self):
        """read_gml returns format-native shape (bends/polyline), not GEG path."""
        G = read_gml(str(SAMPLE))
        assert "path" not in G.edges[0, 1]
        assert "position" not in G.nodes[0]


# ---------- write_gml + read_gml round trip ----------

class TestWriteGMLRoundTrip:
    def test_round_trip_preserves_node_attrs(self, tmp_path):
        G = read_gml(str(SAMPLE))
        out = tmp_path / "rt.gml"
        write_gml(G, str(out))
        G2 = read_gml(str(out))
        for n in G.nodes:
            for key in ("x", "y", "width", "height", "colour", "shape", "label"):
                assert G2.nodes[n].get(key) == G.nodes[n].get(key)

    def test_round_trip_preserves_edge_attrs(self, tmp_path):
        G = read_gml(str(SAMPLE))
        out = tmp_path / "rt.gml"
        write_gml(G, str(out))
        G2 = read_gml(str(out))
        for u, v in G.edges:
            assert G2.edges[u, v].get("bends") == G.edges[u, v].get("bends")
            assert G2.edges[u, v].get("polyline") == G.edges[u, v].get("polyline")
            for key in ("colour", "stroke_width", "label", "weight"):
                assert G2.edges[u, v].get(key) == G.edges[u, v].get(key)

    def test_write_gml_honours_directed(self, tmp_path):
        import networkx as nx
        G = nx.DiGraph()
        G.add_node(0, x=0, y=0)
        G.add_node(1, x=1, y=0)
        G.add_edge(0, 1)
        out = tmp_path / "di.gml"
        write_gml(G, str(out))
        text = out.read_text()
        assert "directed 1" in text
