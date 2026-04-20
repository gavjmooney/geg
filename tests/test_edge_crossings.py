"""Tests for geg.edge_crossings.

Paper §3.2 eq. (3):
  EC(D) = 1 - c/c_max              if c_max > 0 and c <= c_max
        = 1                         if c > c_max (curves allow more than c_max)
        = 0                         otherwise
with
  c_all = C(|E|, 2)
  c_deg = sum_v C(deg(v), 2)
  c_max = c_all - c_deg
Crossings with angle below `min_angle_tol` (default 2.5°) are discarded.
"""

import math

import networkx as nx
import pytest

from geg import edge_crossings


def _layout(coords):
    G = nx.Graph()
    for n, (x, y) in coords.items():
        G.add_node(n, x=float(x), y=float(y))
    return G


def _straight(u, v, coords):
    x0, y0 = coords[u]
    x1, y1 = coords[v]
    return f"M{x0},{y0} L{x1},{y1}"


class TestDegenerate:
    def test_no_edges_returns_one(self):
        # c_max = 0 → return 1.0 (no crossings possible).
        G = _layout({"a": (0.0, 0.0)})
        assert edge_crossings(G) == 1.0

    def test_single_edge(self):
        coords = {"a": (0.0, 0.0), "b": (1.0, 0.0)}
        G = _layout(coords)
        G.add_edge("a", "b", path=_straight("a", "b", coords))
        assert edge_crossings(G) == 1.0

    def test_path_graph_no_crossings(self):
        # Path a-b-c. c_all=1, c_deg=1 (middle node), c_max=0 → 1.0.
        coords = {"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (2.0, 0.0)}
        G = _layout(coords)
        G.add_edge("a", "b", path=_straight("a", "b", coords))
        G.add_edge("b", "c", path=_straight("b", "c", coords))
        assert edge_crossings(G) == 1.0


class TestK4Square:
    def test_unit_square_diagonals_cross_once(self):
        """K4 on unit square: all 6 edges present. The two diagonals cross
        at (0.5, 0.5) at 90°. Every other edge pair either shares a vertex
        (excluded) or is parallel / non-crossing.

        m=6, c_all=15, c_deg = 4 * C(3,2) = 12, c_max = 3.
        Crossings = 1, EC = 1 - 1/3 = 2/3.
        """
        coords = {
            "a": (0.0, 0.0), "b": (1.0, 0.0),
            "c": (1.0, 1.0), "d": (0.0, 1.0),
        }
        G = _layout(coords)
        for u, v in [("a", "b"), ("b", "c"), ("c", "d"), ("d", "a"),
                      ("a", "c"), ("b", "d")]:
            G.add_edge(u, v, path=_straight(u, v, coords))
        assert edge_crossings(G) == pytest.approx(2.0 / 3.0)


class TestSharedEndpointNotACrossing:
    def test_two_edges_sharing_endpoint(self):
        """Edges (a,b) and (b,c) share vertex b. Their segments meet at b but
        that's not an interior intersection → no crossing counted."""
        coords = {"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (2.0, 1.0)}
        G = _layout(coords)
        G.add_edge("a", "b", path=_straight("a", "b", coords))
        G.add_edge("b", "c", path=_straight("b", "c", coords))
        # c_max = 0 (degree-sum absorbs everything) so result is 1.0 regardless.
        assert edge_crossings(G) == 1.0


class TestMinAngleTolerance:
    def test_near_parallel_crossing_filtered(self):
        """Two nearly-parallel edges with tiny crossing angle (<2.5°) are
        filtered by the default min_angle_tol. Construct an X where the two
        arms meet at ~1.1°.
        """
        # Edge 1: horizontal.
        # Edge 2: tiny slope so angle ~ 1°.
        slope = math.tan(math.radians(1.0))
        coords = {
            "a": (0.0, 0.0), "b": (2.0, 0.0),
            "c": (0.0, -slope * 1.0), "d": (2.0, slope * 1.0),
        }
        G = _layout(coords)
        G.add_edge("a", "b", path=_straight("a", "b", coords))
        G.add_edge("c", "d", path=_straight("c", "d", coords))
        # With 2 edges, c_all=1, c_deg=0, c_max=1. The actual crossing is
        # below the 2.5° tolerance → counted as 0 → EC = 1.
        assert edge_crossings(G) == pytest.approx(1.0)

    def test_at_threshold_is_kept(self):
        """Force a clear 45° crossing so tolerance doesn't matter."""
        coords = {
            "a": (0.0, 0.0), "b": (2.0, 0.0),
            "c": (0.0, -1.0), "d": (2.0, 1.0),
        }
        G = _layout(coords)
        G.add_edge("a", "b", path=_straight("a", "b", coords))
        G.add_edge("c", "d", path=_straight("c", "d", coords))
        # m=2, c_max=1, crossings=1 → EC=0.
        assert edge_crossings(G) == pytest.approx(0.0)


class TestReturnCrossings:
    def test_returns_tuple_with_crossings_list(self):
        coords = {
            "a": (0.0, 0.0), "b": (2.0, 0.0),
            "c": (0.0, -1.0), "d": (2.0, 1.0),
        }
        G = _layout(coords)
        G.add_edge("a", "b", path=_straight("a", "b", coords))
        G.add_edge("c", "d", path=_straight("c", "d", coords))
        ec, crossings = edge_crossings(G, return_crossings=True)
        assert ec == pytest.approx(0.0)
        assert len(crossings) == 1
        (x, y), angle = crossings[0]
        assert (x, y) == pytest.approx((1.0, 0.0))
        assert angle == pytest.approx(45.0)


class TestClampAtZero:
    def test_c_greater_than_c_max_clamps(self):
        """Curved edges can in principle produce more crossings than c_max
        (which assumes neighbouring edges don't cross). The metric clamps to 0
        in that case (paper §3.2 eq. (3): EC = 0 when c > c_max).
        """
        # Construct a graph with m=2, c_max=1, and two polyline edges that
        # cross each other twice.
        G = _layout({"a": (0.0, 0.0), "b": (10.0, 0.0),
                      "c": (0.0, 1.0), "d": (10.0, 1.0)})
        # Polyline edges that weave across each other.
        G.add_edge("a", "b", polyline=True, path="M0,0 L3,2 L7,-1 L10,0")
        G.add_edge("c", "d", polyline=True, path="M0,1 L3,-1 L7,2 L10,1")
        # c_max=1, but these weave → c >= 2. EC clamps at 0.
        assert edge_crossings(G) == pytest.approx(0.0)


class TestInvariants:
    """EC counts crossings between edge pairs. Whether two line segments
    cross is preserved by every rigid motion (translation, rotation,
    reflection) and by uniform scaling. The `c_max` denominator depends
    only on `|E|` and the degree sequence — both pure topological
    quantities — so EC itself is invariant.
    """

    def _k4_square(self, coords):
        G = _layout(coords)
        for u, v in [("a", "b"), ("b", "c"), ("c", "d"), ("d", "a"),
                      ("a", "c"), ("b", "d")]:
            G.add_edge(u, v, path=_straight(u, v, coords))
        return G

    def _baseline(self):
        return {
            "a": (0.0, 0.0), "b": (1.0, 0.0),
            "c": (1.0, 1.0), "d": (0.0, 1.0),
        }

    def test_translation_invariant(self):
        base = self._baseline()
        shifted = {n: (x + 100.0, y + 50.0) for n, (x, y) in base.items()}
        assert edge_crossings(self._k4_square(base)) == pytest.approx(
            edge_crossings(self._k4_square(shifted))
        )

    def test_uniform_scale_invariant(self):
        base = self._baseline()
        scaled = {n: (x * 42.0, y * 42.0) for n, (x, y) in base.items()}
        assert edge_crossings(self._k4_square(base)) == pytest.approx(
            edge_crossings(self._k4_square(scaled))
        )

    def test_arbitrary_rotation_invariant(self):
        theta = math.radians(37.0)
        c, s = math.cos(theta), math.sin(theta)
        base = self._baseline()
        rotated = {n: (x * c - y * s, x * s + y * c) for n, (x, y) in base.items()}
        assert edge_crossings(self._k4_square(base)) == pytest.approx(
            edge_crossings(self._k4_square(rotated))
        )
