"""Tests for geg.crossing_angle.

Paper §3.2 eq. (2):
  CA(D) = 1 - (1/|X|) * sum_x |φ - φ^min_x| / φ
with φ = 90° (ideal crossing angle) and φ^min_x the smallest (acute) angle
between the two crossing edges at x.

These tests build real graphs and let the metric detect crossings and
compute their angles itself, i.e. the full `edge_crossings → crossing_angle`
pipeline. The `crossings=` kwarg (pre-computed injection) is only covered
by a small defensive-clamp test.
"""

import math

import networkx as nx
import pytest

from geg import crossing_angle


def _layout(coords):
    G = nx.Graph()
    for n, (x, y) in coords.items():
        G.add_node(n, x=float(x), y=float(y))
    return G


def _with_straight_edges(G, edges):
    """Add straight `M x0,y0 L x1,y1` paths for each edge."""
    for u, v in edges:
        x0, y0 = G.nodes[u]["x"], G.nodes[u]["y"]
        x1, y1 = G.nodes[v]["x"], G.nodes[v]["y"]
        G.add_edge(u, v, path=f"M{x0},{y0} L{x1},{y1}")
    return G


class TestDetectedCrossings:
    """Real geometry — crossings are detected and measured by the pipeline."""

    def test_no_crossings_returns_one(self):
        # Two disjoint horizontal edges at different heights — no crossing.
        G = _layout({
            "a": (0.0, 0.0), "b": (1.0, 0.0),
            "c": (0.0, 1.0), "d": (1.0, 1.0),
        })
        _with_straight_edges(G, [("a", "b"), ("c", "d")])
        assert crossing_angle(G) == pytest.approx(1.0)

    def test_single_perpendicular_crossing(self):
        # Horizontal (-1,0)→(1,0) crossed by vertical (0,-1)→(0,1) at the
        # origin at 90° → zero shortfall → CA = 1.
        G = _layout({
            "a": (-1.0, 0.0), "b": (1.0, 0.0),
            "c": (0.0, -1.0), "d": (0.0, 1.0),
        })
        _with_straight_edges(G, [("a", "b"), ("c", "d")])
        assert crossing_angle(G) == pytest.approx(1.0)

    def test_single_45_degree_crossing(self):
        # Horizontal (0,0)→(2,0) crossed by diagonal (0,-1)→(2,1) at (1, 0).
        # The diagonal's direction (2, 2) is 45° from horizontal →
        # shortfall = (90-45)/90 = 0.5 → CA = 0.5.
        G = _layout({
            "a": (0.0, 0.0), "b": (2.0, 0.0),
            "c": (0.0, -1.0), "d": (2.0, 1.0),
        })
        _with_straight_edges(G, [("a", "b"), ("c", "d")])
        assert crossing_angle(G) == pytest.approx(0.5, rel=1e-6)

    def test_mixed_90_and_30(self):
        # Horizontal spine (0,0)→(4,0) crossed twice:
        #   vertical (1,-1)→(1,1) at x=1 at 90° → shortfall 0
        #   diagonal (3-√3,-1)→(3+√3,1) at x=3 at 30° → shortfall 2/3
        # The two transverse edges do NOT cross each other: diagonal's
        # x-range is [3-√3, 3+√3] ≈ [1.27, 4.73], which does not reach x=1.
        # avg shortfall = (0 + 2/3)/2 = 1/3 → CA = 2/3.
        G = _layout({
            "a": (0.0, 0.0), "b": (4.0, 0.0),
            "c": (1.0, -1.0), "d": (1.0, 1.0),
            "e": (3.0 - math.sqrt(3.0), -1.0),
            "f": (3.0 + math.sqrt(3.0),  1.0),
        })
        _with_straight_edges(G, [("a", "b"), ("c", "d"), ("e", "f")])
        assert crossing_angle(G) == pytest.approx(2.0 / 3.0, rel=1e-6)


class TestNearParallelFiltering:
    """`edge_crossings` drops crossings with acute angle < `min_angle_tol`
    (default 2.5°). Consequence: the paper's worst-case "angle = 0 → CA = 0"
    is not observable through the public pipeline — such a crossing is
    filtered upstream, so CA returns 1.0 (no surviving crossings).
    Unit tests that want to exercise shortfall = 1 must inject a 0°
    crossing via the `crossings=` kwarg (see TestDefensiveClamp).
    """

    def test_near_parallel_crossing_is_filtered(self):
        # (0,0)→(2,0) crossed by (0,ε)→(2,-ε) at (1, 0). The crossing angle
        # is atan(ε) ≈ 0.573° at ε=0.01, well below the 2.5° threshold —
        # filtered out before reaching the CA aggregation.
        eps = 0.01
        G = _layout({
            "a": (0.0, 0.0), "b": (2.0, 0.0),
            "c": (0.0, eps), "d": (2.0, -eps),
        })
        _with_straight_edges(G, [("a", "b"), ("c", "d")])
        assert crossing_angle(G) == pytest.approx(1.0)


class TestIdealAngleParameter:
    def test_custom_ideal_angle(self):
        # Custom ideal = 60°. Two edges cross at 30°:
        #   horizontal (0,0)→(2,0)
        #   diagonal (1-√3,-1)→(1+√3,1), direction (2√3, 2), 30° from horizontal
        # shortfall = (60-30)/60 = 0.5 → CA = 0.5.
        G = _layout({
            "a": (0.0, 0.0), "b": (2.0, 0.0),
            "c": (1.0 - math.sqrt(3.0), -1.0),
            "d": (1.0 + math.sqrt(3.0),  1.0),
        })
        _with_straight_edges(G, [("a", "b"), ("c", "d")])
        assert crossing_angle(G, ideal_angle=60.0) == pytest.approx(0.5, rel=1e-6)


class TestEndToEnd:
    def test_k4_square_diagonals_perpendicular(self):
        """Unit-square K4: the two diagonals (a,c) and (b,d) cross at
        (0.5, 0.5) at 90°. Other edge pairs share an endpoint (excluded
        from X) or don't cross, so |X| = 1 and CA = 1.
        """
        G = _layout({
            "a": (0.0, 0.0), "b": (1.0, 0.0),
            "c": (1.0, 1.0), "d": (0.0, 1.0),
        })
        _with_straight_edges(
            G, [("a","b"), ("b","c"), ("c","d"), ("d","a"), ("a","c"), ("b","d")]
        )
        assert crossing_angle(G) == pytest.approx(1.0)


class TestDefensiveClamp:
    """The `crossings=` kwarg accepts arbitrary `(position, angle)` tuples,
    including angles outside the `[0, ideal_angle]` range produced by the
    canonical pipeline. The implementation clamps per-crossing shortfall to
    ≥ 0 and the final score to [0, 1]; this test guards those clamps. Not
    reachable through the normal pipeline (which only emits acute angles).
    """

    def test_obtuse_precomputed_angle_clamped(self):
        G = nx.Graph()
        score = crossing_angle(G, crossings=[((0.0, 0.0), 120.0)])
        assert 0.0 <= score <= 1.0

    def test_zero_angle_precomputed_is_worst(self):
        # Paper formula's worst case: angle = 0 → per-crossing shortfall = 1 →
        # CA = 0. Only reachable via injection; the pipeline filters 0° out.
        G = nx.Graph()
        score = crossing_angle(G, crossings=[((0.0, 0.0), 0.0)])
        assert score == pytest.approx(0.0)


class TestInvariants:
    """CA depends only on the angles at each crossing, which are preserved
    by translation, uniform scale, and arbitrary rotation. Tested
    end-to-end so the rotation carries through the geometric intersection
    logic, not just the aggregation step.
    """

    def _layout_with_crossing(self, coords):
        """Horizontal edge a-b + diagonal c-d crossing it at (1, 0) at 45°."""
        G = _layout(coords)
        _with_straight_edges(G, [("a", "b"), ("c", "d")])
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
        theta = math.radians(37.0)
        c, s = math.cos(theta), math.sin(theta)
        base = self._baseline_coords()
        rotated = {n: (x * c - y * s, x * s + y * c) for n, (x, y) in base.items()}
        G1 = self._layout_with_crossing(base)
        G2 = self._layout_with_crossing(rotated)
        assert crossing_angle(G1) == pytest.approx(crossing_angle(G2), rel=1e-6)
