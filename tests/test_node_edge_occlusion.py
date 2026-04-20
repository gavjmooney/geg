"""Tests for geg.node_edge_occlusion.

The metric's per-edge penalty is `c = max(0, 1 - max(0, d - r)/ε)**3`, where
`d` is the minimum distance from a non-endpoint node's centre to the edge
geometry, `r` is the node's `radius` (default 0), and `ε = epsilon_fraction
* bbox_diagonal`.
"""

import math

import networkx as nx
import pytest

from geg import node_edge_occlusion


def _layout(coords, edges=(), edge_paths=None, radii=None):
    G = nx.Graph()
    for n, (x, y) in coords.items():
        kwargs = {"x": float(x), "y": float(y)}
        if radii and n in radii:
            kwargs["radius"] = float(radii[n])
        G.add_node(n, **kwargs)
    edge_paths = edge_paths or {}
    for u, v in edges:
        if (u, v) in edge_paths:
            G.add_edge(u, v, path=edge_paths[(u, v)], polyline=True)
        else:
            G.add_edge(u, v)
    return G


class TestDegenerate:
    def test_single_node(self):
        assert node_edge_occlusion(_layout({"a": (0.0, 0.0)})) == 1.0

    def test_zero_size_bbox(self):
        G = _layout({"a": (0.0, 0.0), "b": (0.0, 0.0), "c": (0.0, 0.0)})
        G.add_edge("a", "b")
        assert node_edge_occlusion(G) == 1.0

    def test_no_edges(self):
        G = _layout({"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (2.0, 0.0)})
        assert node_edge_occlusion(G) == 1.0


class TestNoOcclusion:
    def test_equilateral_triangle(self):
        # Each vertex is far from the opposite edge → no penalty.
        coords = {
            "a": (0.0, 0.0), "b": (1.0, 0.0),
            "c": (0.5, math.sqrt(3) / 2),
        }
        edges = [("a", "b"), ("b", "c"), ("c", "a")]
        assert node_edge_occlusion(_layout(coords, edges)) == pytest.approx(1.0)

    def test_star_k1_4_legs_dont_pass_over_other_leaves(self):
        coords = {
            "c": (0.0, 0.0), "e": (1.0, 0.0),
            "s": (0.0, 1.0), "w": (-1.0, 0.0), "n": (0.0, -1.0),
        }
        edges = [("c", "e"), ("c", "s"), ("c", "w"), ("c", "n")]
        assert node_edge_occlusion(_layout(coords, edges)) == pytest.approx(1.0)


class TestKnownPenaltyCentreOnly:
    """Edge a=(0,0), b=(4,0); bbox diagonal ≈ 4 so at ε_fraction=0.02, ε=0.08."""

    def test_node_at_gap_half_epsilon(self):
        # c at (2, 0.04) → d=0.04, r=0 → gap/ε = 0.5 → penalty = 0.125.
        G = _layout(
            {"a": (0.0, 0.0), "b": (4.0, 0.0), "c": (2.0, 0.04)},
            [("a", "b")],
        )
        # diag = sqrt(16 + 0.04**2) ≈ 4.0002 → ε ≈ 0.080004.
        diag = math.hypot(4.0, 0.04)
        epsilon = 0.02 * diag
        expected_penalty = (1.0 - 0.04 / epsilon) ** 3
        expected = 1.0 - expected_penalty
        assert node_edge_occlusion(G) == pytest.approx(expected, rel=1e-9)

    def test_node_directly_on_edge_is_full_penalty(self):
        # c on edge → d=0, r=0 → penalty = 1 → score = 0.
        G = _layout(
            {"a": (0.0, 0.0), "b": (4.0, 0.0), "c": (2.0, 0.0)},
            [("a", "b")],
        )
        assert node_edge_occlusion(G) == pytest.approx(0.0)

    def test_node_far_from_edge_is_no_penalty(self):
        G = _layout(
            {"a": (0.0, 0.0), "b": (4.0, 0.0), "c": (2.0, 2.0)},
            [("a", "b")],
        )
        assert node_edge_occlusion(G) == pytest.approx(1.0)


class TestRadiusAware:
    """Radius shrinks the effective gap: `gap = max(0, d - r)`."""

    def test_radius_worsens_the_score(self):
        # Same position as TestKnownPenaltyCentreOnly, but c has radius 0.02.
        # Without radius: d=0.04 → gap=0.04. With radius 0.02: gap=0.02.
        # Penalty (no r) = (1 - 0.5)^3 = 0.125.  With r: (1 - 0.25)^3 = 0.421875.
        coords = {"a": (0.0, 0.0), "b": (4.0, 0.0), "c": (2.0, 0.04)}
        edges = [("a", "b")]
        without = node_edge_occlusion(_layout(coords, edges))
        with_r = node_edge_occlusion(_layout(coords, edges, radii={"c": 0.02}))
        assert with_r < without

    def test_radius_disk_straddling_line_gives_full_penalty(self):
        # Node at (2, 0.03) with radius 0.05: r > d → disk straddles edge.
        # gap = max(0, 0.03 - 0.05) = 0 → penalty = (1 - 0)^3 = 1 → score = 0.
        coords = {"a": (0.0, 0.0), "b": (4.0, 0.0), "c": (2.0, 0.03)}
        G = _layout(coords, [("a", "b")], radii={"c": 0.05})
        assert node_edge_occlusion(G) == pytest.approx(0.0)

    def test_radius_has_no_effect_when_safely_far(self):
        # Node at (2, 2.0) with radius 0.1: gap = 1.9. At ε ≈ 0.08 (fraction
        # 0.02 × diag), 1.9/ε >> 1 → clipped to 0 penalty.
        coords = {"a": (0.0, 0.0), "b": (4.0, 0.0), "c": (2.0, 2.0)}
        G = _layout(coords, [("a", "b")], radii={"c": 0.1})
        assert node_edge_occlusion(G) == pytest.approx(1.0)


class TestCurvedEdges:
    def test_polyline_detected_over_a_bend(self):
        """Straight chord misses the node by a mile, but the polyline bend
        passes right next to it. The metric should flag it via the polyline,
        not the chord.
        """
        # Chord from (0,0) to (4,0). Polyline bends up to (2, 3).
        # Third node at (2, 2.9) sits 0.1 from the bend → polyline distance is
        # small, but straight-chord distance from (2, 2.9) to segment y=0
        # is 2.9.
        coords = {"a": (0.0, 0.0), "b": (4.0, 0.0), "c": (2.0, 2.9)}
        edges = [("a", "b")]
        paths = {("a", "b"): "M0,0 L2,3 L4,0"}
        G = _layout(coords, edges, edge_paths=paths)
        score = node_edge_occlusion(G)
        # Polyline-aware → some penalty. Exact value depends on the geometry;
        # at minimum it must be strictly less than 1.
        assert score < 1.0

    def test_polyline_preserves_no_occlusion_for_distant_node(self):
        # Polyline bends up but the third node is well off to the side.
        coords = {"a": (0.0, 0.0), "b": (4.0, 0.0), "c": (-2.0, 2.0)}
        edges = [("a", "b")]
        paths = {("a", "b"): "M0,0 L2,3 L4,0"}
        G = _layout(coords, edges, edge_paths=paths)
        assert node_edge_occlusion(G) == pytest.approx(1.0)


class TestEpsilonFraction:
    def test_default_is_0_02(self):
        """Pin the new default (was 0.03 when the metric was first added)."""
        import inspect

        sig = inspect.signature(node_edge_occlusion)
        assert sig.parameters["epsilon_fraction"].default == 0.02

    def test_larger_fraction_amplifies_penalty(self):
        coords = {"a": (0.0, 0.0), "b": (4.0, 0.0), "c": (2.0, 0.04)}
        G = _layout(coords, [("a", "b")])
        tight = node_edge_occlusion(G, epsilon_fraction=0.02)
        loose = node_edge_occlusion(G, epsilon_fraction=0.05)
        assert loose < tight  # wider penalty zone → smaller score

    def test_explicit_radius_matches_old_formula_when_r_zero(self):
        """With r=0 everywhere, the radius-aware formula degenerates to
        `max(0, 1 - d/ε)^3`, i.e. the original (pre-radius) definition."""
        coords = {"a": (0.0, 0.0), "b": (4.0, 0.0), "c": (2.0, 0.04)}
        G = _layout(coords, [("a", "b")])
        # diag = sqrt(16 + 0.04^2), ε = 0.02 * diag.
        diag = math.hypot(4.0, 0.04)
        epsilon = 0.02 * diag
        expected = 1.0 - (1.0 - 0.04 / epsilon) ** 3
        assert node_edge_occlusion(G) == pytest.approx(expected, rel=1e-9)
