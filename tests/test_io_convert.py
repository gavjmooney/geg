"""Tests for geg.io.convert — generic dispatchers + pair-wise converters.

Covers the three new entry points (`convert`, `read_drawing`, `write_drawing`)
and verifies that every supported (input extension × output extension) pair
round-trips through the dispatcher.
"""

from pathlib import Path

import networkx as nx
import pytest

import geg
from geg.io.convert import (
    convert,
    read_drawing,
    write_drawing,
    gml_to_geg,
    graphml_to_geg,
    convert_gml_to_graphml,
    convert_graphml_to_gml,
)


FIXTURES = Path(__file__).parent / "fixtures"
IO_FIXTURES = FIXTURES / "io"

GEG_INPUT = FIXTURES / "equilateral_triangle.geg"
GRAPHML_INPUT = IO_FIXTURES / "sample.graphml"
GML_INPUT = IO_FIXTURES / "sample.gml"


# ---------- read_drawing ----------

class TestReadDrawing:
    @pytest.mark.parametrize("src,expected_nodes", [
        (GEG_INPUT, 3),
        (GRAPHML_INPUT, 2),
        (GML_INPUT, 2),
    ])
    def test_dispatches_on_extension(self, src, expected_nodes):
        G = read_drawing(str(src))
        assert isinstance(G, nx.Graph)
        assert G.number_of_nodes() == expected_nodes

    def test_accepts_pathlib(self):
        G = read_drawing(GRAPHML_INPUT)  # Path, not str
        assert G.number_of_nodes() == 2

    def test_returns_geg_canonical(self):
        """Every reader path must yield GEG-canonical edge geometry (SVG path)."""
        for src in (GRAPHML_INPUT, GML_INPUT):
            G = read_drawing(src)
            edge = next(iter(G.edges(data=True)))[2]
            assert "path" in edge, f"no `path` on edge from {src}"

    def test_unsupported_extension(self, tmp_path):
        p = tmp_path / "x.dot"
        p.write_text("")
        with pytest.raises(ValueError, match="Unsupported input extension"):
            read_drawing(str(p))


# ---------- write_drawing ----------

class TestWriteDrawing:
    @pytest.fixture
    def small_graph(self):
        G = nx.Graph()
        G.add_node(0, x=0.0, y=0.0)
        G.add_node(1, x=1.0, y=1.0)
        G.add_edge(0, 1, path="M0,0 L1,1", polyline=False)
        return G

    @pytest.mark.parametrize("ext", [".geg", ".graphml", ".gml", ".svg"])
    def test_writes_every_supported_format(self, small_graph, tmp_path, ext):
        out = tmp_path / f"out{ext}"
        write_drawing(small_graph, out)
        assert out.exists() and out.stat().st_size > 0

    def test_forwards_svg_kwargs(self, small_graph, tmp_path):
        out = tmp_path / "g.svg"
        write_drawing(small_graph, out, grid=True)
        # Grid lines land as <line stroke=...> tags in the SVG body.
        assert "<line" in out.read_text()

    def test_unsupported_extension(self, small_graph, tmp_path):
        with pytest.raises(ValueError, match="Unsupported output extension"):
            write_drawing(small_graph, tmp_path / "x.dot")


# ---------- convert (pair-wise, end-to-end) ----------

class TestConvertPairs:
    @pytest.mark.parametrize("src", [GEG_INPUT, GRAPHML_INPUT, GML_INPUT])
    @pytest.mark.parametrize("dst_ext", [".geg", ".graphml", ".gml", ".svg"])
    def test_any_to_any(self, src, dst_ext, tmp_path):
        dst = tmp_path / f"converted{dst_ext}"
        G = convert(str(src), str(dst))
        assert dst.exists() and dst.stat().st_size > 0
        assert isinstance(G, nx.Graph)

    def test_graphml_to_gml_preserves_structure(self, tmp_path):
        out = tmp_path / "roundtrip.gml"
        convert(str(GRAPHML_INPUT), str(out))
        G2 = read_drawing(out)
        # Both sample files describe the same 2-node 1-edge drawing.
        assert G2.number_of_nodes() == 2
        assert G2.number_of_edges() == 1

    def test_kwargs_passed_through_to_writer(self, tmp_path):
        out = tmp_path / "out.svg"
        convert(str(GRAPHML_INPUT), str(out), grid=True)
        assert "<line" in out.read_text()


# ---------- pair-wise helpers remain callable ----------

class TestPairwiseBackcompat:
    def test_graphml_to_geg_still_works(self):
        G = graphml_to_geg(str(GRAPHML_INPUT))
        assert G.number_of_nodes() == 2
        # GEG-canonical: edge has an SVG path string.
        assert "path" in G.edges["a", "b"]

    def test_gml_to_geg_still_works(self):
        G = gml_to_geg(str(GML_INPUT))
        assert G.number_of_nodes() == 2
        assert "path" in G.edges[0, 1]

    def test_gml_to_graphml_roundtrip(self, tmp_path):
        out = tmp_path / "out.graphml"
        convert_gml_to_graphml(str(GML_INPUT), str(out))
        assert out.exists() and out.stat().st_size > 0

    def test_graphml_to_gml_roundtrip(self, tmp_path):
        out = tmp_path / "out.gml"
        convert_graphml_to_gml(str(GRAPHML_INPUT), str(out))
        assert out.exists() and out.stat().st_size > 0


# ---------- public surface on the top-level `geg` package ----------

class TestPublicSurface:
    def test_all_exports_present(self):
        for name in (
            "convert", "read_drawing", "write_drawing",
            "gml_to_geg", "graphml_to_geg",
            "convert_gml_to_graphml", "convert_graphml_to_gml",
            "read_geg", "write_geg",
            "read_gml", "write_gml",
            "read_graphml", "write_graphml",
        ):
            assert hasattr(geg, name), f"geg.{name} missing"

    def test_convert_callable_from_top_level(self, tmp_path):
        out = tmp_path / "via_geg.gml"
        geg.convert(str(GEG_INPUT), str(out))
        assert out.exists()
