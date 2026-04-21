"""Tests for geg.io.geg (GEG JSON reader + writer + file-level introspection).

Covers round-trip preservation of node and edge attributes against every
Phase-3 fixture, plus the various coordinate-input variants accepted by
read_geg, plus has_self_loops_file / is_multigraph_file.
"""

import json
from pathlib import Path

import networkx as nx
import pytest

from geg import (
    has_self_loops_file,
    is_multigraph_file,
    read_geg,
    write_geg,
)
from geg.io.geg import _coerce_bool, _extract_xy

from .fixtures._builder import all_fixtures


# ---------- Coerce helpers ----------

class TestCoerceBool:
    @pytest.mark.parametrize("val", ["true", "True", "TRUE", "yes", "1", "t"])
    def test_truthy_strings(self, val):
        assert _coerce_bool(val) is True

    @pytest.mark.parametrize("val", ["false", "no", "0", "f", "N"])
    def test_falsy_strings(self, val):
        assert _coerce_bool(val) is False

    def test_actual_booleans_pass_through(self):
        assert _coerce_bool(True) is True
        assert _coerce_bool(False) is False

    def test_numbers_cast_to_bool(self):
        assert _coerce_bool(1) is True
        assert _coerce_bool(0) is False
        assert _coerce_bool(3.14) is True

    def test_unknown_passes_through(self):
        assert _coerce_bool("maybe") == "maybe"


class TestExtractXY:
    def test_xy_attrs_preferred(self):
        assert _extract_xy({"x": 1.0, "y": 2.0}) == (1.0, 2.0)

    def test_falls_back_to_pos_list(self):
        assert _extract_xy({"pos": [3.0, 4.0]}) == (3.0, 4.0)

    def test_falls_back_to_pos_dict(self):
        assert _extract_xy({"pos": {"x": 5.0, "y": 6.0}}) == (5.0, 6.0)

    def test_falls_back_to_position_list(self):
        assert _extract_xy({"position": [7.0, 8.0]}) == (7.0, 8.0)

    def test_returns_none_when_missing(self):
        assert _extract_xy({}) == (None, None)

    def test_returns_none_on_bad_types(self):
        assert _extract_xy({"x": "banana"}) == (None, None)


# ---------- Round-trip every Phase-3 fixture ----------

def _geg_equal(G1: nx.Graph, G2: nx.Graph) -> None:
    """Assert G2 preserves every attr present on G1 (G2 may carry extra
    synthesised attrs like `id` / `position` that G1 didn't have).
    """
    assert set(G1.nodes) == set(G2.nodes)
    assert G1.number_of_edges() == G2.number_of_edges()

    for n in G1.nodes:
        for k, v in G1.nodes[n].items():
            assert G2.nodes[n].get(k) == v, f"node {n!r} attr {k!r} lost"

    # Undirected edges: match by endpoint pair, then compare attr dicts
    # subset-wise (G1 ⊆ G2 per edge).
    pairs2 = {tuple(sorted([u, v])): G2.edges[u, v] for u, v in G2.edges}
    for u, v, attrs1 in G1.edges(data=True):
        key = tuple(sorted([u, v]))
        assert key in pairs2, f"edge {key} lost"
        attrs2 = pairs2[key]
        for k, val in attrs1.items():
            assert attrs2.get(k) == val, f"edge {key} attr {k!r} lost"


@pytest.mark.parametrize("fixture_name", list(all_fixtures().keys()))
def test_fixture_roundtrip(fixture_name, tmp_path):
    fx = all_fixtures()[fixture_name]
    G = fx.build()
    out = tmp_path / f"{fixture_name}.geg"
    write_geg(G, str(out))
    G2 = read_geg(str(out))
    _geg_equal(G, G2)


# ---------- Position-input variants ----------

class TestPositionInputVariants:
    def _write(self, tmp_path, nodes, edges=None):
        p = tmp_path / "custom.geg"
        p.write_text(json.dumps({
            "graph": {"directed": False},
            "nodes": nodes,
            "edges": edges or [],
        }))
        return str(p)

    def test_reads_position_as_list(self, tmp_path):
        path = self._write(tmp_path, [{"id": "a", "position": [1.5, -2.5]}])
        G = read_geg(path)
        assert G.nodes["a"]["x"] == 1.5
        assert G.nodes["a"]["y"] == -2.5
        assert G.nodes["a"]["position"] == [1.5, -2.5]

    def test_reads_position_as_dict(self, tmp_path):
        path = self._write(tmp_path, [{"id": "a", "position": {"x": 3.0, "y": 4.0}}])
        G = read_geg(path)
        assert G.nodes["a"]["x"] == 3.0
        assert G.nodes["a"]["y"] == 4.0

    def test_reads_pos_alias(self, tmp_path):
        path = self._write(tmp_path, [{"id": "a", "pos": [7.0, 8.0]}])
        G = read_geg(path)
        assert G.nodes["a"]["x"] == 7.0
        assert G.nodes["a"]["y"] == 8.0

    def test_reads_top_level_xy(self, tmp_path):
        path = self._write(tmp_path, [{"id": "a", "x": 9.0, "y": 10.0}])
        G = read_geg(path)
        assert G.nodes["a"]["x"] == 9.0
        assert G.nodes["a"]["y"] == 10.0


# ---------- Arbitrary attribute preservation ----------

class TestAttributePreservation:
    def test_preserves_node_attrs(self, tmp_path):
        G = nx.Graph()
        G.add_node(
            "a",
            x=0.0, y=0.0,
            label="Alpha",
            colour="#FF0000",
            shape="rectangle",
            width=40.0,
            height=30.0,
        )
        G.add_node("b", x=1.0, y=0.0, label="Beta", colour="#00FF00")
        G.add_edge("a", "b",
                    path="M0,0 L1,0",
                    polyline=False,
                    weight=2.5,
                    stroke_width=3.0,
                    colour="#0000FF",
                    label="e",
                    )
        out = tmp_path / "attrs.geg"
        write_geg(G, str(out))
        G2 = read_geg(str(out))

        assert G2.nodes["a"]["label"] == "Alpha"
        assert G2.nodes["a"]["colour"] == "#FF0000"
        assert G2.nodes["a"]["shape"] == "rectangle"
        assert G2.nodes["a"]["width"] == 40.0
        assert G2.nodes["a"]["height"] == 30.0

        ea = G2.edges["a", "b"]
        assert ea["weight"] == 2.5
        assert ea["stroke_width"] == 3.0
        assert ea["colour"] == "#0000FF"
        assert ea["label"] == "e"
        assert ea["polyline"] is False

    def test_preserves_graph_level_metadata(self, tmp_path):
        G = nx.Graph()
        G.graph["doi"] = "10.1234/example"
        G.graph["description"] = "Test fixture"
        G.add_node("a", x=0.0, y=0.0)
        G.add_node("b", x=1.0, y=0.0)
        G.add_edge("a", "b")
        out = tmp_path / "meta.geg"
        write_geg(G, str(out))
        G2 = read_geg(str(out))
        assert G2.graph.get("doi") == "10.1234/example"
        assert G2.graph.get("description") == "Test fixture"


# ---------- Directed + multigraph + self-loops ----------

class TestGraphTypes:
    def test_directed_roundtrip(self, tmp_path):
        G = nx.DiGraph()
        G.add_node("a", x=0.0, y=0.0)
        G.add_node("b", x=1.0, y=0.0)
        G.add_edge("a", "b")
        out = tmp_path / "di.geg"
        write_geg(G, str(out))
        G2 = read_geg(str(out))
        assert isinstance(G2, nx.DiGraph)
        assert ("a", "b") in G2.edges and ("b", "a") not in G2.edges

    def test_multigraph_detected_from_file(self, tmp_path):
        # Write a graph with two parallel edges between a and b.
        data = {
            "graph": {"directed": False},
            "nodes": [
                {"id": "a", "x": 0.0, "y": 0.0},
                {"id": "b", "x": 1.0, "y": 0.0},
            ],
            "edges": [
                {"id": "e0", "source": "a", "target": "b"},
                {"id": "e1", "source": "a", "target": "b"},
            ],
        }
        p = tmp_path / "multi.geg"
        p.write_text(json.dumps(data))
        assert is_multigraph_file(str(p)) is True
        G = read_geg(str(p))
        assert isinstance(G, nx.MultiGraph)
        assert G.number_of_edges() == 2

    def test_self_loops_detected_from_file(self, tmp_path):
        data = {
            "graph": {"directed": False},
            "nodes": [{"id": "a", "x": 0.0, "y": 0.0}],
            "edges": [{"id": "e0", "source": "a", "target": "a"}],
        }
        p = tmp_path / "loop.geg"
        p.write_text(json.dumps(data))
        assert has_self_loops_file(str(p)) is True

    def test_no_self_loops_is_false(self, tmp_path):
        data = {
            "graph": {"directed": False},
            "nodes": [
                {"id": "a", "x": 0.0, "y": 0.0},
                {"id": "b", "x": 1.0, "y": 0.0},
            ],
            "edges": [{"id": "e0", "source": "a", "target": "b"}],
        }
        p = tmp_path / "noloop.geg"
        p.write_text(json.dumps(data))
        assert has_self_loops_file(str(p)) is False


# ---------- explicit-node-radius fixture ----------

RADIUS_FIXTURE = Path(__file__).parent / "fixtures" / "io" / "node_with_radius.geg"


class TestExplicitRadiusFixture:
    """Pins the write-side fallback added in v0.2.0: when a node has an
    explicit `radius` attribute but no width/height, the GML / GraphML
    writers emit `width = height = 2 * radius`. Guards against regressions
    of the earlier behaviour (always 30.0)."""

    def test_reads_radius_attribute(self):
        G = read_geg(str(RADIUS_FIXTURE))
        assert G.nodes["a"]["radius"] == 5.0
        assert G.nodes["b"]["radius"] == 10.0
        assert G.nodes["c"]["radius"] == 15.0

    def test_gml_writer_uses_2x_radius_when_no_width_height(self, tmp_path):
        from geg.io.gml import write_gml
        G = read_geg(str(RADIUS_FIXTURE))
        out = tmp_path / "radius.gml"
        write_gml(G, str(out))
        text = out.read_text()
        # Each node should carry w and h equal to 2 * radius.
        assert "w 10.0\n      h 10.0" in text  # a: r=5
        assert "w 20.0\n      h 20.0" in text  # b: r=10
        assert "w 30.0\n      h 30.0" in text  # c: r=15

    def test_graphml_writer_uses_2x_radius_when_no_width_height(self, tmp_path):
        from geg.io.graphml import write_graphml
        G = read_geg(str(RADIUS_FIXTURE))
        out = tmp_path / "radius.graphml"
        write_graphml(G, str(out))
        text = out.read_text()
        # Each geometry element should carry the 2*radius dimension.
        assert 'width="10.0"' in text and 'height="10.0"' in text
        assert 'width="20.0"' in text and 'height="20.0"' in text
        assert 'width="30.0"' in text and 'height="30.0"' in text

    def test_explicit_width_still_wins_over_radius(self, tmp_path):
        from geg.io.gml import _node_wh
        # Explicit width/height take priority over radius.
        assert _node_wh({"radius": 5.0, "width": 99.0, "height": 88.0}, 4.0) == (99.0, 88.0)
