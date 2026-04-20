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
        # For each edge, the non-endpoint node sits at the opposite vertex
        # of the triangle — perpendicular distance from that vertex to the
        # opposite side is the triangle height = √3/2 ≈ 0.866. Bbox diag is
        # ≈ 1, so ε ≈ 0.02; 0.866 >> 0.02 → gap/ε is huge → penalty = 0 for
        # every (edge, node) pair, and the score is 1 exactly.
        coords = {
            "a": (0.0, 0.0), "b": (1.0, 0.0),
            "c": (0.5, math.sqrt(3) / 2),
        }
        edges = [("a", "b"), ("b", "c"), ("c", "a")]
        assert node_edge_occlusion(_layout(coords, edges)) == pytest.approx(1.0)

    def test_star_k1_4_legs_dont_pass_over_other_leaves(self):
        # Star with axis-aligned legs; each edge is along an axis and the
        # non-endpoint leaves sit on different axes, so perpendicular
        # distance from any leaf to a perpendicular leg is the leg length
        # (= 1), far beyond ε (≈ 0.04 on a 2-wide bbox). Penalty = 0 everywhere.
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


# Note on rotation invariance: NEO is translation- and uniform-scale-
# invariant (both node-to-edge distances and the ε = 0.02 · bbox_diag
# scale factor transform identically), but *not* rotation-invariant in
# general — the axis-aligned bounding-box diagonal depends on the
# drawing's orientation, so ε changes with rotation even though node-to-
# edge distances do not. Only rotations that preserve the axis-aligned
# bbox (e.g. 90° for shapes with matching width/height) leave the score
# unchanged. No invariance tests added for this reason.


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


class TestRadiusFallback:
    """If `radius` is missing but `width`/`height` are present (the shape of
    graphs returned by read_graphml / read_gml / graphml_to_geg / gml_to_geg),
    NEO must use the circumscribed-disk radius `max(width, height) / 2`."""

    def test_width_height_drive_occlusion(self):
        """Node with width=30, height=30 (r_eff = 15) centred 10 units away
        from a horizontal edge: r_eff > d so that edge is fully occluded."""
        G = nx.Graph()
        G.add_node("u", x=0.0, y=0.0)
        G.add_node("v", x=400.0, y=0.0)
        G.add_node("mid", x=200.0, y=10.0, width=30.0, height=30.0)
        G.add_node("far", x=200.0, y=400.0)
        G.add_edge("u", "v")
        G.add_edge("u", "far")
        G.add_edge("v", "far")
        # 3 edges; only (u,v) is straddled by `mid`'s disk → worst = 1.0.
        # `far` is well clear of all edges. Expected: 1 - 1/3 ≈ 0.667.
        assert node_edge_occlusion(G) == pytest.approx(2.0 / 3.0, rel=1e-6)

    def test_explicit_radius_wins_over_width_height(self):
        """Prefer explicit `radius` to width/height when both exist."""
        G = nx.Graph()
        G.add_node("u", x=0.0, y=0.0)
        G.add_node("v", x=400.0, y=0.0)
        G.add_node("mid", x=200.0, y=10.0, width=30.0, height=30.0, radius=0.0)
        G.add_edge("u", "v")
        # radius=0 overrides width/height → d=10, large epsilon not tripped.
        assert node_edge_occlusion(G) == pytest.approx(1.0, abs=0.1)

    def test_rectangular_node_uses_max_dimension(self):
        """A wide-but-thin rectangle: max(width, height) / 2 gives a disk
        large enough to occlude."""
        G = nx.Graph()
        G.add_node("u", x=0.0, y=0.0)
        G.add_node("v", x=400.0, y=0.0)
        # Node 6 units off the edge, width=40 (r=20), height=2 (r=1).
        # max-based radius = 20 > 6 → full occlusion.
        G.add_node("mid", x=200.0, y=6.0, width=40.0, height=2.0)
        G.add_edge("u", "v")
        assert node_edge_occlusion(G) == pytest.approx(0.0, abs=1e-9)
