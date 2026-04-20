"""Tests for geg.angular_resolution (both min-angle and avg-angle variants).

Paper §3.2 eq. (1) is the min-angle variant:
  AR(D) = 1 - (1/|V_{>1}|) * sum_v |θ_v - θ_v^min| / θ_v
with θ_v = 360 / deg(v) and θ_v^min the actual minimum angle at v.
The avg variant is a library extension (mean absolute deviation of gaps).
"""

import math

import networkx as nx
import pytest

from geg import angular_resolution_avg_angle, angular_resolution_min_angle


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
    def test_no_eligible_nodes_returns_one(self):
        # Two-node graph, both have degree 1 → ignored → return 1.
        coords = {"a": (0.0, 0.0), "b": (1.0, 0.0)}
        G = _layout(coords)
        G.add_edge("a", "b", path=_straight("a", "b", coords))
        assert angular_resolution_min_angle(G) == 1.0
        assert angular_resolution_avg_angle(G) == 1.0


class TestPerfectResolution:
    def test_star_k1_4_axis_aligned(self):
        # Centre c with 4 legs at 0°, 90°, 180°, 270° → perfect degree-4 spread.
        coords = {
            "c": (0.0, 0.0),
            "e": (1.0, 0.0),
            "n": (0.0, -1.0),
            "w": (-1.0, 0.0),
            "s": (0.0, 1.0),
        }
        G = _layout(coords)
        for leaf in ("e", "n", "w", "s"):
            G.add_edge("c", leaf, path=_straight("c", leaf, coords))
        assert angular_resolution_min_angle(G) == pytest.approx(1.0)
        assert angular_resolution_avg_angle(G) == pytest.approx(1.0)

    def test_y_shape_perfect_degree_three(self):
        # Three legs 120° apart from origin.
        coords = {
            "c": (0.0, 0.0),
            "a": (1.0, 0.0),
            "b": (math.cos(math.radians(120)), math.sin(math.radians(120))),
            "d": (math.cos(math.radians(240)), math.sin(math.radians(240))),
        }
        G = _layout(coords)
        for leaf in ("a", "b", "d"):
            G.add_edge("c", leaf, path=_straight("c", leaf, coords))
        assert angular_resolution_min_angle(G) == pytest.approx(1.0)
        assert angular_resolution_avg_angle(G) == pytest.approx(1.0)

    def test_degree_two_straight_path(self):
        """Middle node of a 3-node straight path: two legs at 0° and 180°
        (the ideal for degree 2)."""
        coords = {"a": (-1.0, 0.0), "b": (0.0, 0.0), "c": (1.0, 0.0)}
        G = _layout(coords)
        G.add_edge("a", "b", path=_straight("a", "b", coords))
        G.add_edge("b", "c", path=_straight("b", "c", coords))
        assert angular_resolution_min_angle(G) == pytest.approx(1.0)
        assert angular_resolution_avg_angle(G) == pytest.approx(1.0)


class TestKnownDeviations:
    def test_equilateral_triangle(self):
        """At each vertex, the two incident edges meet at 60°, not the
        degree-2 ideal of 180°. Gaps at each vertex = [60, 300].

        min variant: (180 - 60)/180 = 2/3 shortfall per vertex → AR = 1/3.
        avg variant: |60-180| = |300-180| = 120; mean = 120; norm = 120/180
            = 2/3 per vertex → AR = 1/3.
        """
        coords = {
            "a": (0.0, 0.0),
            "b": (1.0, 0.0),
            "c": (0.5, math.sqrt(3) / 2),
        }
        G = _layout(coords)
        for u, v in [("a", "b"), ("b", "c"), ("c", "a")]:
            G.add_edge(u, v, path=_straight(u, v, coords))
        assert angular_resolution_min_angle(G) == pytest.approx(1.0 / 3.0)
        assert angular_resolution_avg_angle(G) == pytest.approx(1.0 / 3.0)

    def test_t_shape_degree_three_uneven(self):
        """T-shape at origin with legs to (+x), (+y), (-x). Angles 0°, 90°, 180°.
        Sorted ascending-clockwise-from-y gaps are [90, 90, 180]; ideal = 120°.

        min variant: (120-90)/120 = 1/4 → AR = 3/4.
        avg variant: |90-120|,|90-120|,|180-120| = 30,30,60; mean=40; norm=40/120=1/3.
                     AR = 2/3.
        """
        coords = {
            "c": (0.0, 0.0),
            "east": (1.0, 0.0),
            "north": (0.0, -1.0),
            "west": (-1.0, 0.0),
        }
        G = _layout(coords)
        for leaf in ("east", "north", "west"):
            G.add_edge("c", leaf, path=_straight("c", leaf, coords))
        assert angular_resolution_min_angle(G) == pytest.approx(0.75)
        assert angular_resolution_avg_angle(G) == pytest.approx(2.0 / 3.0)


class TestDisconnected:
    def test_two_isolated_perfect_stars(self):
        """Two widely separated stars, each with perfect degree-3 spread.
        AR is locally defined (paper §3.3), so disconnection is irrelevant.
        """
        def leg(theta_deg):
            return (math.cos(math.radians(theta_deg)),
                    math.sin(math.radians(theta_deg)))

        coords = {
            "c1": (0.0, 0.0),
            "c1_a": leg(0), "c1_b": leg(120), "c1_c": leg(240),
            "c2": (100.0, 100.0),
        }
        c2x, c2y = coords["c2"]
        coords["c2_a"] = (c2x + math.cos(0),              c2y + math.sin(0))
        coords["c2_b"] = (c2x + math.cos(math.radians(120)), c2y + math.sin(math.radians(120)))
        coords["c2_c"] = (c2x + math.cos(math.radians(240)), c2y + math.sin(math.radians(240)))

        G = _layout(coords)
        for centre, leaves in [("c1", ("c1_a", "c1_b", "c1_c")),
                                ("c2", ("c2_a", "c2_b", "c2_c"))]:
            for leaf in leaves:
                G.add_edge(centre, leaf, path=_straight(centre, leaf, coords))

        assert angular_resolution_min_angle(G) == pytest.approx(1.0)
        assert angular_resolution_avg_angle(G) == pytest.approx(1.0)


class TestCanonicalAlias:
    """`geg.angular_resolution` is a callable alias for the paper §3.2
    eq. (1) min-angle variant, exposed so that `geg.angular_resolution(G)`
    works exactly like `geg.angular_resolution_min_angle(G)`. The submodule
    (`geg.angular_resolution.reverse_svg_path` etc.) remains importable."""

    def test_alias_is_same_function(self):
        import geg
        assert geg.angular_resolution is geg.angular_resolution_min_angle

    def test_alias_returns_min_angle_value(self):
        # T-shape: mindgap = 90°, ideal = 120°, shortfall = 30/120 = 0.25 →
        # min-angle AR = 0.75. avg-angle AR would be 2/3 (≠ 0.75), so this
        # test would fail if the alias pointed at the avg variant.
        import geg
        coords = {
            "c": (0.0, 0.0),
            "east": (1.0, 0.0),
            "north": (0.0, -1.0),
            "west": (-1.0, 0.0),
        }
        G = _layout(coords)
        for leaf in ("east", "north", "west"):
            G.add_edge("c", leaf, path=_straight("c", leaf, coords))
        assert geg.angular_resolution(G) == pytest.approx(0.75)

    def test_submodule_still_importable(self):
        """Package-attribute rebinding must not break
        `from geg.angular_resolution import X` (resolved via sys.modules)."""
        from geg.angular_resolution import (
            reverse_svg_path,
            orient_svg_path_for_node,
        )
        assert callable(reverse_svg_path)
        assert callable(orient_svg_path_for_node)


class TestInvariants:
    """AR is defined as the shortfall of actual-gap vs ideal-gap at each
    vertex, where gaps are angles between incident edges. Angles between
    vectors are preserved by translation, uniform scale, and arbitrary
    rotation — so AR should be invariant under all three isometries plus
    uniform scale.
    """

    def _t_shape_coords(self):
        # degree-3 vertex, gaps [90°, 90°, 180°]; min-angle AR = 3/4.
        return {
            "c": (0.0, 0.0),
            "east": (1.0, 0.0),
            "north": (0.0, -1.0),
            "west": (-1.0, 0.0),
        }

    def _build(self, coords):
        G = _layout(coords)
        for leaf in ("east", "north", "west"):
            G.add_edge("c", leaf, path=_straight("c", leaf, coords))
        return G

    def test_translation_invariant(self):
        coords = self._t_shape_coords()
        shifted = {n: (x + 100.0, y - 37.0) for n, (x, y) in coords.items()}
        # rebuild paths from translated coords so M…L… strings match.
        G1 = self._build(coords)
        G2 = self._build(shifted)
        assert angular_resolution_min_angle(G1) == pytest.approx(
            angular_resolution_min_angle(G2)
        )

    def test_uniform_scale_invariant(self):
        coords = self._t_shape_coords()
        scaled = {n: (x * 17.3, y * 17.3) for n, (x, y) in coords.items()}
        G1 = self._build(coords)
        G2 = self._build(scaled)
        assert angular_resolution_min_angle(G1) == pytest.approx(
            angular_resolution_min_angle(G2)
        )

    def test_arbitrary_rotation_invariant(self):
        # Rotate by 37° about the origin: (x, y) -> (x cos θ - y sin θ,
        # x sin θ + y cos θ). Angles between incident edges are preserved.
        theta = math.radians(37.0)
        c, s = math.cos(theta), math.sin(theta)
        coords = self._t_shape_coords()
        rotated = {n: (x * c - y * s, x * s + y * c) for n, (x, y) in coords.items()}
        G1 = self._build(coords)
        G2 = self._build(rotated)
        assert angular_resolution_min_angle(G1) == pytest.approx(
            angular_resolution_min_angle(G2)
        )
