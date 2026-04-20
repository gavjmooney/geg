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


class TestOutputRange:
    def test_obtuse_precomputed_angles_clamped(self):
        """A caller passing a precomputed crossings list with an angle >
        ideal must still receive a score in [0, 1]; the public formula can
        otherwise go above 1."""
        import networkx as nx
        G = nx.Graph()
        # crossings list: (position, angle_in_degrees) — angle deliberately obtuse.
        score = crossing_angle(G, crossings=[((0.0, 0.0), 120.0)])
        assert 0.0 <= score <= 1.0

    def test_perfect_90_degree_is_one(self):
        import networkx as nx
        G = nx.Graph()
        score = crossing_angle(G, crossings=[((0.0, 0.0), 90.0), ((1.0, 0.0), 90.0)])
        assert score == pytest.approx(1.0)


class TestInvariants:
    """CA depends only on the angles at each crossing, which are preserved
    by translation, uniform scale, and arbitrary rotation. Tested
    end-to-end through edge_crossings so the rotation carries through the
    geometric intersection logic, not just the aggregation step.
    """

    def _layout_with_crossing(self, coords):
        """Horizontal edge a-b + diagonal c-d crossing it at (1, 0) at 45°."""
        import math as _m
        G = _layout(coords)
        for u, v in [("a", "b"), ("c", "d")]:
            x0, y0 = coords[u]
            x1, y1 = coords[v]
            G.add_edge(u, v, path=f"M{x0},{y0} L{x1},{y1}")
        return G

    def _baseline_coords(self):
        return {
            "a": (0.0, 0.0), "b": (2.0, 0.0),
            "c": (0.0, -1.0), "d": (2.0, 1.0),
        }

    def test_translation_invariant(self):
        base = self._baseline_coords()
        shifted = {n: (x + 50.0, y - 20.0) for n, (x, y) in base.items()}
        G1 = self._layout_with_crossing(base)
        G2 = self._layout_with_crossing(shifted)
        assert crossing_angle(G1) == pytest.approx(crossing_angle(G2), rel=1e-6)

    def test_uniform_scale_invariant(self):
        base = self._baseline_coords()
        scaled = {n: (x * 17.3, y * 17.3) for n, (x, y) in base.items()}
        G1 = self._layout_with_crossing(base)
        G2 = self._layout_with_crossing(scaled)
        assert crossing_angle(G1) == pytest.approx(crossing_angle(G2), rel=1e-6)

    def test_arbitrary_rotation_invariant(self):
        import math as _m
        theta = _m.radians(37.0)
        c, s = _m.cos(theta), _m.sin(theta)
        base = self._baseline_coords()
        rotated = {n: (x * c - y * s, x * s + y * c) for n, (x, y) in base.items()}
        G1 = self._layout_with_crossing(base)
        G2 = self._layout_with_crossing(rotated)
        assert crossing_angle(G1) == pytest.approx(crossing_angle(G2), rel=1e-6)
