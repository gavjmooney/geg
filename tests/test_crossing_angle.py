"""Tests for geg.crossing_angle.

Paper §3.2 eq. (2):
  CA(D) = 1 - (1/|X|) * sum_x |φ - φ^min_x| / φ
with φ = 90° (ideal crossing angle) and φ^min_x the smallest (acute) angle
between the two crossing edges at x. The `crossings` parameter bypasses the
edge_crossings pipeline for direct unit testing of the aggregation logic.
"""

import networkx as nx
import pytest

from geg import crossing_angle


def _layout(coords):
    G = nx.Graph()
    for n, (x, y) in coords.items():
        G.add_node(n, x=float(x), y=float(y))
    return G


class TestDirectCrossings:
    def test_no_crossings_returns_one(self):
        G = _layout({"a": (0.0, 0.0), "b": (1.0, 0.0)})
        G.add_edge("a", "b", path="M0,0 L1,0")
        assert crossing_angle(G, crossings=[]) == 1.0

    def test_single_perpendicular_crossing(self):
        # One crossing at the ideal 90° → no shortfall, CA = 1.
        G = _layout({"a": (0.0, 0.0), "b": (1.0, 0.0)})
        G.add_edge("a", "b", path="M0,0 L1,0")
        ca = crossing_angle(G, crossings=[(((0.5, 0.5)), 90.0)])
        assert ca == pytest.approx(1.0)

    def test_single_45_degree_crossing(self):
        # shortfall = (90-45)/90 = 0.5 → CA = 0.5.
        G = _layout({"a": (0.0, 0.0), "b": (1.0, 0.0)})
        G.add_edge("a", "b", path="M0,0 L1,0")
        ca = crossing_angle(G, crossings=[(((0.5, 0.5)), 45.0)])
        assert ca == pytest.approx(0.5)

    def test_mixed_90_and_30(self):
        # shortfalls = 0 and 60/90 = 2/3; avg = 1/3; CA = 2/3.
        G = _layout({"a": (0.0, 0.0), "b": (1.0, 0.0)})
        G.add_edge("a", "b", path="M0,0 L1,0")
        ca = crossing_angle(
            G, crossings=[(((0.5, 0.5)), 90.0), (((0.7, 0.7)), 30.0)]
        )
        assert ca == pytest.approx(2.0 / 3.0)

    def test_zero_angle_crossing_is_worst(self):
        # shortfall = 1 → CA = 0 (parallel overlap; edge_crossings normally
        # filters this via min_angle_tol, but the metric itself maps it to 0).
        G = _layout({"a": (0.0, 0.0), "b": (1.0, 0.0)})
        G.add_edge("a", "b", path="M0,0 L1,0")
        ca = crossing_angle(G, crossings=[(((0.5, 0.5)), 0.0)])
        assert ca == pytest.approx(0.0)


class TestIdealAngleParameter:
    def test_custom_ideal_angle(self):
        # ideal=60°, actual=30° → shortfall = 30/60 = 0.5 → CA = 0.5.
        G = _layout({"a": (0.0, 0.0), "b": (1.0, 0.0)})
        G.add_edge("a", "b", path="M0,0 L1,0")
        ca = crossing_angle(
            G, ideal_angle=60.0, crossings=[(((0.5, 0.5)), 30.0)]
        )
        assert ca == pytest.approx(0.5)


class TestEndToEnd:
    def test_k4_square_diagonals_perpendicular(self):
        """Unit square K4: the two diagonals (a,c) and (b,d) cross at (0.5,
        0.5) at 90°. Other edge pairs either share an endpoint (excluded) or
        don't cross, so |X| = 1 and CA = 1.
        """
        G = _layout({
            "a": (0.0, 0.0), "b": (1.0, 0.0),
            "c": (1.0, 1.0), "d": (0.0, 1.0),
        })
        edges = [
            ("a", "b", "M0,0 L1,0"),
            ("b", "c", "M1,0 L1,1"),
            ("c", "d", "M1,1 L0,1"),
            ("d", "a", "M0,1 L0,0"),
            ("a", "c", "M0,0 L1,1"),
            ("b", "d", "M1,0 L0,1"),
        ]
        for u, v, path in edges:
            G.add_edge(u, v, path=path)
        assert crossing_angle(G) == pytest.approx(1.0)

    def test_45_degree_crossing_through_full_pipeline(self):
        """Horizontal edge (0,0)-(2,0) crossed by a diagonal (0,-1)-(2,1) at
        (1, 0). Angle between direction (2,0) and (2,2) is 45°.
        CA should be 0.5."""
        G = _layout({
            "a": (0.0, 0.0), "b": (2.0, 0.0),
            "c": (0.0, -1.0), "d": (2.0, 1.0),
        })
        G.add_edge("a", "b", path="M0,0 L2,0")
        G.add_edge("c", "d", path="M0,-1 L2,1")
        assert crossing_angle(G) == pytest.approx(0.5, rel=1e-6)
