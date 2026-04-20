"""Tests for geg.aspect_ratio.

Paper §3.2 (Asp):
  1              if h=0 or w=0
  h/w            if h <= w
  w/h            otherwise
Bounding box dimensions h, w include edge geometry (curves promoted).
"""

import math

import networkx as nx
import pytest

from geg import aspect_ratio


def _layout(coords):
    G = nx.Graph()
    for n, (x, y) in coords.items():
        G.add_node(n, x=float(x), y=float(y))
    return G


class TestDegenerate:
    def test_single_node(self):
        # Paper spec: h=0 and w=0 → Asp=1.
        G = _layout({"a": (0.0, 0.0)})
        assert aspect_ratio(G) == 1.0

    def test_horizontal_line_of_nodes(self):
        # All on the x-axis → h=0 → Asp=1.
        G = _layout({"a": (0.0, 0.0), "b": (5.0, 0.0), "c": (-3.0, 0.0)})
        assert aspect_ratio(G) == 1.0

    def test_vertical_line_of_nodes(self):
        # All on the y-axis → w=0 → Asp=1.
        G = _layout({"a": (0.0, 0.0), "b": (0.0, 5.0), "c": (0.0, -3.0)})
        assert aspect_ratio(G) == 1.0


class TestRatios:
    def test_unit_square(self):
        G = _layout({
            "a": (0.0, 0.0), "b": (1.0, 0.0),
            "c": (0.0, 1.0), "d": (1.0, 1.0),
        })
        assert aspect_ratio(G) == pytest.approx(1.0)

    def test_wide_rectangle_2_to_1(self):
        # w=2, h=1 → h/w = 0.5.
        G = _layout({
            "a": (0.0, 0.0), "b": (2.0, 0.0),
            "c": (0.0, 1.0), "d": (2.0, 1.0),
        })
        assert aspect_ratio(G) == pytest.approx(0.5)

    def test_tall_rectangle_1_to_3(self):
        # w=1, h=3 → w/h = 1/3.
        G = _layout({
            "a": (0.0, 0.0), "b": (1.0, 0.0),
            "c": (0.0, 3.0), "d": (1.0, 3.0),
        })
        assert aspect_ratio(G) == pytest.approx(1.0 / 3.0)


class TestCurvedEdgesAffectBBox:
    def test_polyline_bend_extends_bounding_box(self):
        """Two nodes at (0,0) and (2,0) — the node-only bbox is 2 × 0. With a
        polyline bend at (1, 3), the promoted bbox becomes 2 × 3 → Asp = 2/3.
        Using a polyline rather than a Bezier because its extents are exact
        (Bezier bboxes are tighter than their control polygons).
        """
        G = _layout({"a": (0.0, 0.0), "b": (2.0, 0.0)})
        G.add_edge(
            "a", "b",
            polyline=True,
            path="M0,0 L1,3 L2,0",
        )
        assert aspect_ratio(G) == pytest.approx(2.0 / 3.0)


class TestInvariants:
    def test_translation_invariant(self):
        coords = {
            "a": (0.0, 0.0), "b": (2.0, 0.0),
            "c": (0.0, 1.0), "d": (2.0, 1.0),
        }
        G1 = _layout(coords)
        G2 = _layout({n: (x + 100, y - 500) for n, (x, y) in coords.items()})
        assert aspect_ratio(G1) == pytest.approx(aspect_ratio(G2))

    def test_uniform_scale_invariant(self):
        coords = {
            "a": (0.0, 0.0), "b": (2.0, 0.0),
            "c": (0.0, 1.0), "d": (2.0, 1.0),
        }
        G1 = _layout(coords)
        G2 = _layout({n: (x * 42.0, y * 42.0) for n, (x, y) in coords.items()})
        assert aspect_ratio(G1) == pytest.approx(aspect_ratio(G2))

    def test_swapping_width_and_height_gives_same_value(self):
        """Paper definition is symmetric under 90° rotation: w↔h → Asp same."""
        wide = _layout({
            "a": (0.0, 0.0), "b": (3.0, 0.0),
            "c": (0.0, 1.0), "d": (3.0, 1.0),
        })
        tall = _layout({
            "a": (0.0, 0.0), "b": (1.0, 0.0),
            "c": (0.0, 3.0), "d": (1.0, 3.0),
        })
        assert aspect_ratio(wide) == pytest.approx(aspect_ratio(tall))
