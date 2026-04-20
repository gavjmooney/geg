"""Tests for geg.to_svg (rewritten in Phase 3).

The SVG output is rendered in pixel coordinates (viewBox in pixels), with
GEG coordinates scaled by `scale` (pixels per GEG unit). A `grid=True` kwarg
adds a faint integer-coordinate grid to the background for manual verification.
"""

import math
import xml.etree.ElementTree as ET
from pathlib import Path

import networkx as nx
import pytest

from geg import to_svg


SVG_NS = "http://www.w3.org/2000/svg"


def _layout(coords):
    G = nx.Graph()
    for n, (x, y) in coords.items():
        G.add_node(n, x=float(x), y=float(y))
    return G


def _parse_svg(path: Path):
    tree = ET.parse(path)
    return tree.getroot()


def _findall(root, tag):
    return root.findall(f".//{{{SVG_NS}}}{tag}")


class TestBasicOutput:
    def test_writes_valid_xml_with_svg_root(self, tmp_path):
        G = _layout({"a": (0.0, 0.0), "b": (1.0, 0.0)})
        G.add_edge("a", "b")
        out = tmp_path / "out.svg"
        to_svg(G, str(out))
        assert out.exists()
        root = _parse_svg(out)
        assert root.tag == f"{{{SVG_NS}}}svg"

    def test_has_expected_edge_and_node_elements(self, tmp_path):
        G = _layout({
            "a": (0.0, 0.0), "b": (1.0, 0.0), "c": (0.5, 1.0),
        })
        G.add_edges_from([("a", "b"), ("b", "c"), ("c", "a")])
        out = tmp_path / "out.svg"
        to_svg(G, str(out))
        root = _parse_svg(out)
        # One <path> per edge.
        assert len(_findall(root, "path")) == 3
        # One node element per node (default shape is circle/ellipse).
        assert len(_findall(root, "ellipse")) + len(_findall(root, "circle")) == 3


class TestScaling:
    def test_viewbox_accounts_for_scale_and_margin(self, tmp_path):
        # Bounding box of nodes = 0..2 in x, 0..0 in y.
        G = _layout({"a": (0.0, 0.0), "b": (2.0, 0.0)})
        G.add_edge("a", "b")
        out = tmp_path / "out.svg"
        to_svg(G, str(out), scale=50.0, margin=20.0)
        root = _parse_svg(out)
        vb = root.get("viewBox").split()
        x, y, w, h = (float(v) for v in vb)
        # Pixel-space viewBox: (min - margin, min - margin, w, h).
        # GEG bbox is 0..2 in x → scaled = 0..100 px. Plus 2*20 = 40 margin → w = 140.
        assert w == pytest.approx(140.0)
        # y is a zero-height stripe, so h = 2*margin = 40.
        assert h == pytest.approx(40.0)


class TestGridKwarg:
    def test_no_grid_by_default(self, tmp_path):
        G = _layout({"a": (0.0, 0.0), "b": (2.0, 0.0)})
        G.add_edge("a", "b")
        out = tmp_path / "out.svg"
        to_svg(G, str(out))
        root = _parse_svg(out)
        # No group labelled "grid".
        groups = _findall(root, "g")
        grid_groups = [g for g in groups if g.get("class") == "grid"]
        assert grid_groups == []

    def test_grid_true_emits_grid_group(self, tmp_path):
        G = _layout({"a": (0.0, 0.0), "b": (3.0, 0.0), "c": (0.0, 2.0)})
        G.add_edges_from([("a", "b"), ("b", "c")])
        out = tmp_path / "out_grid.svg"
        to_svg(G, str(out), grid=True)
        root = _parse_svg(out)
        groups = _findall(root, "g")
        grid_groups = [g for g in groups if g.get("class") == "grid"]
        assert len(grid_groups) == 1
        # Grid has lines for each integer coordinate inside the viewBox.
        # With GEG bbox x in [0, 3], y in [0, 2], we expect at least 4 verticals
        # (x = 0, 1, 2, 3) and 3 horizontals (y = 0, 1, 2).
        grid = grid_groups[0]
        lines = grid.findall(f".//{{{SVG_NS}}}line")
        assert len(lines) >= 4 + 3

    def test_grid_appears_before_edges(self, tmp_path):
        """Grid must be rendered *under* edges and nodes (earlier in document
        order). Otherwise the grid would occlude the drawing."""
        G = _layout({"a": (0.0, 0.0), "b": (2.0, 0.0)})
        G.add_edge("a", "b")
        out = tmp_path / "out_order.svg"
        to_svg(G, str(out), grid=True)
        root = _parse_svg(out)
        # Iterate top-level children in order.
        children = list(root)
        tags = [c.tag.split("}")[-1] for c in children]
        # The grid group tag 'g' should appear before any 'path' (edge).
        if "path" in tags:
            assert tags.index("g") < tags.index("path")


class TestCurvedEdges:
    def test_polyline_path_preserved(self, tmp_path):
        G = _layout({"a": (0.0, 0.0), "b": (2.0, 0.0)})
        G.add_edge("a", "b", polyline=True, path="M0,0 L1,3 L2,0")
        out = tmp_path / "curve.svg"
        to_svg(G, str(out), scale=50.0, margin=10.0)
        root = _parse_svg(out)
        paths = _findall(root, "path")
        assert len(paths) == 1
        d = paths[0].get("d")
        # After scaling by 50, the polyline M0,0 L1,3 L2,0 → M0,0 L50,150 L100,0.
        # We don't care about the exact whitespace; check key sub-strings.
        assert "M" in d and "L" in d
        # Bbox must include y up to 3 (polyline bend) scaled × 50 = 150 + margin.
        vb = root.get("viewBox").split()
        _, _, _, h = (float(v) for v in vb)
        assert h >= 150.0


class TestWidthHeightAutoFit:
    def test_default_width_is_800(self, tmp_path):
        G = _layout({"a": (0.0, 0.0), "b": (10.0, 0.0), "c": (5.0, 5.0)})
        G.add_edges_from([("a", "b"), ("b", "c"), ("c", "a")])
        out = tmp_path / "out.svg"
        to_svg(G, str(out))
        root = _parse_svg(out)
        assert float(root.get("width")) == pytest.approx(800.0)

    def test_height_auto_preserves_aspect_ratio(self, tmp_path):
        """Square drawing → square canvas."""
        G = _layout({"a": (0.0, 0.0), "b": (100.0, 0.0), "c": (0.0, 100.0), "d": (100.0, 100.0)})
        out = tmp_path / "sq.svg"
        to_svg(G, str(out), width=800, margin=0)
        root = _parse_svg(out)
        # bbox 100×100 into a 800-wide canvas (margin=0) → height also 800.
        assert float(root.get("width")) == pytest.approx(800.0)
        assert float(root.get("height")) == pytest.approx(800.0)

    def test_wide_drawing_gets_short_canvas(self, tmp_path):
        G = _layout({"a": (0.0, 0.0), "b": (100.0, 0.0), "c": (50.0, 10.0)})
        G.add_edges_from([("a", "b"), ("b", "c")])
        out = tmp_path / "wide.svg"
        to_svg(G, str(out), width=1000, margin=0)
        root = _parse_svg(out)
        # bbox 100×10 (curves promoted so c's y=10 is the top), width 1000 →
        # scale 10 px/unit → height 10 × 10 = 100.
        assert float(root.get("height")) == pytest.approx(100.0)

    def test_explicit_width_and_height_letterbox(self, tmp_path):
        """When both given, drawing is aspect-preserved and centred."""
        G = _layout({"a": (0.0, 0.0), "b": (100.0, 0.0), "c": (0.0, 100.0)})
        G.add_edges_from([("a", "b"), ("a", "c")])
        out = tmp_path / "letter.svg"
        to_svg(G, str(out), width=800, height=400, margin=0)
        root = _parse_svg(out)
        assert float(root.get("width")) == pytest.approx(800.0)
        assert float(root.get("height")) == pytest.approx(400.0)
        # Height is the tighter constraint (100-unit bbox in 400 px vs. 800 px),
        # so scale = 4, scaled bbox = 400×400, centred in 800×400 canvas.
        vb = root.get("viewBox").split()
        _, _, w, h = (float(v) for v in vb)
        assert w == pytest.approx(800.0)
        assert h == pytest.approx(400.0)

    def test_explicit_scale_disables_auto_fit(self, tmp_path):
        """Passing `scale` reverts to the old bbox×scale + margin sizing."""
        G = _layout({"a": (0.0, 0.0), "b": (2.0, 0.0)})
        G.add_edge("a", "b")
        out = tmp_path / "fixed.svg"
        to_svg(G, str(out), scale=50.0, margin=20.0)
        root = _parse_svg(out)
        # bbox 2×0 × scale 50 → 100×0 + margin 2*20 = 140 × 40.
        assert float(root.get("width")) == pytest.approx(140.0)
        assert float(root.get("height")) == pytest.approx(40.0)

    def test_custom_width_scales_accordingly(self, tmp_path):
        G = _layout({"a": (0.0, 0.0), "b": (10.0, 0.0), "c": (5.0, 10.0)})
        G.add_edges_from([("a", "b"), ("b", "c")])
        out = tmp_path / "narrow.svg"
        to_svg(G, str(out), width=400, margin=0)
        root = _parse_svg(out)
        assert float(root.get("width")) == pytest.approx(400.0)
        # 10-unit-wide bbox into 400 px (margin=0) → scale 40 → height 400.
        assert float(root.get("height")) == pytest.approx(400.0)
