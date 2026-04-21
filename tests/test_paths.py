import math

import pytest

from geg import _paths as P


class TestParsePath:
    def test_straight_line(self):
        path = P.parse_path("M0,0 L10,0")
        assert len(path) == 1

    def test_bezier_curve(self):
        path = P.parse_path("M0,0 C1,2 3,4 5,0")
        assert len(path) == 1

    def test_polyline(self):
        path = P.parse_path("M0,0 L5,5 L10,0")
        assert len(path) == 2


class TestFlattenPathToPolyline:
    """Returns a list of (x, y) sample points tracing the whole path."""

    def test_straight_line_is_endpoints(self):
        poly = P.flatten_path_to_polyline("M0,0 L10,0", samples_per_curve=50)
        assert poly[0] == pytest.approx((0.0, 0.0))
        assert poly[-1] == pytest.approx((10.0, 0.0))
        # Straight lines are kept as their two endpoints.
        assert len(poly) == 2

    def test_polyline_keeps_bends(self):
        poly = P.flatten_path_to_polyline("M0,0 L5,5 L10,0", samples_per_curve=50)
        assert poly[0] == pytest.approx((0.0, 0.0))
        assert (5.0, 5.0) in poly
        assert poly[-1] == pytest.approx((10.0, 0.0))

    def test_curve_samples_count(self):
        poly = P.flatten_path_to_polyline("M0,0 C1,2 3,4 5,0", samples_per_curve=10)
        # N samples per curve → N points.
        assert len(poly) == 10
        # Endpoints preserved.
        assert poly[0] == pytest.approx((0.0, 0.0))
        assert poly[-1] == pytest.approx((5.0, 0.0))

    def test_no_duplicate_at_segment_joins(self):
        poly = P.flatten_path_to_polyline("M0,0 L1,0 L2,0", samples_per_curve=50)
        # Joint point (1,0) should appear once, not twice.
        assert poly.count((1.0, 0.0)) == 1


class TestFlattenPathToSegments:
    """Returns a list of ((x0, y0), (x1, y1)) consecutive segments."""

    def test_straight_line_is_one_segment(self):
        segs = P.flatten_path_to_segments("M0,0 L10,0", samples_per_curve=50)
        assert segs == [((0.0, 0.0), (10.0, 0.0))]

    def test_polyline_is_N_minus_1_segments(self):
        segs = P.flatten_path_to_segments("M0,0 L5,5 L10,0", samples_per_curve=50)
        assert len(segs) == 2

    def test_curve_is_samples_minus_one_segments(self):
        segs = P.flatten_path_to_segments("M0,0 C1,2 3,4 5,0", samples_per_curve=10)
        # Matches the existing flatten_path_to_lines contract: N samples → N-1 segs.
        assert len(segs) == 9


class TestPolylineLength:
    def test_horizontal_line(self):
        assert P.polyline_length([(0.0, 0.0), (10.0, 0.0)]) == 10.0

    def test_l_shape(self):
        # (0,0) -> (3,0) -> (3,4): lengths 3 + 4 = 7
        assert P.polyline_length([(0.0, 0.0), (3.0, 0.0), (3.0, 4.0)]) == 7.0

    def test_single_point_is_zero(self):
        assert P.polyline_length([(1.0, 2.0)]) == 0.0

    def test_empty_is_zero(self):
        assert P.polyline_length([]) == 0.0


class TestPathToPolylineOnEdge:
    """Whole-edge convenience: takes endpoints + path_str, snaps endpoints."""

    def test_no_path_returns_endpoints_straight(self):
        poly = P.edge_polyline(
            source=(0.0, 0.0),
            target=(10.0, 0.0),
            path_str=None,
            samples_per_curve=50,
        )
        assert poly == [(0.0, 0.0), (10.0, 0.0)]

    def test_endpoints_snapped_to_source_target(self):
        # The path string might be slightly off from node positions; the
        # returned polyline should still start/end at the node coords.
        poly = P.edge_polyline(
            source=(0.0, 0.0),
            target=(10.0, 0.0),
            path_str="M0.001,0 L9.999,0",
            samples_per_curve=50,
        )
        assert poly[0] == (0.0, 0.0)
        assert poly[-1] == (10.0, 0.0)


# ---------- curvature-aware adaptive flattening ----------

class TestFlattenPathAdaptive:
    """`flatten_path_adaptive` subdivides each non-Line segment until the
    midpoint-to-chord distance drops below `flatness_tol`. Lines are kept
    as their two endpoints (same invariant as the fixed-N helper)."""

    def test_straight_line_is_endpoints(self):
        poly = P.flatten_path_adaptive("M0,0 L10,0", flatness_tol=0.1)
        assert poly == [(0.0, 0.0), (10.0, 0.0)]

    def test_multi_segment_polyline_not_subdivided(self):
        # All Line segments → no adaptive subdivision, just shared-endpoint dedup.
        poly = P.flatten_path_adaptive("M0,0 L5,5 L10,0", flatness_tol=0.1)
        assert poly == [(0.0, 0.0), (5.0, 5.0), (10.0, 0.0)]

    def test_highly_curved_segment_many_samples(self):
        # Tight parabolic arch — midpoint y=5, chord y=0 → deviation = 5.
        # With flatness_tol = 0.1, expect many subdivisions.
        poly = P.flatten_path_adaptive("M0,0 Q10,20 20,0", flatness_tol=0.1)
        assert len(poly) > 10

    def test_nearly_straight_curve_terminates_fast(self):
        # Control point only 0.01 off the chord midpoint → first midpoint
        # check succeeds at tol=0.1, returning just 2 endpoints.
        poly = P.flatten_path_adaptive("M0,0 Q10,0.01 20,0", flatness_tol=0.1)
        assert len(poly) == 2

    def test_tighter_tolerance_yields_denser_sampling(self):
        loose = P.flatten_path_adaptive("M0,0 Q10,20 20,0", flatness_tol=1.0)
        tight = P.flatten_path_adaptive("M0,0 Q10,20 20,0", flatness_tol=0.01)
        assert len(tight) > len(loose)

    def test_flatness_guarantee_is_respected(self):
        """Empirical check: sample the true curve densely and confirm every
        point lies within flatness_tol of the nearest polyline segment."""
        tol = 0.1
        path_str = "M0,0 Q10,20 20,0"
        poly = P.flatten_path_adaptive(path_str, flatness_tol=tol)
        true_curve = list(P.parse_path(path_str))[0]
        max_dev = 0.0
        for k in range(1000):
            t = k / 999
            pt = true_curve.point(t)
            best = min(
                P._point_to_segment_distance(
                    pt.real, pt.imag, a[0], a[1], b[0], b[1]
                )
                for a, b in zip(poly, poly[1:])
            )
            max_dev = max(max_dev, best)
        # Allow a tiny numerical slack.
        assert max_dev <= tol + 1e-6

    def test_endpoints_preserved_exactly(self):
        poly = P.flatten_path_adaptive("M0,0 Q10,5 20,0", flatness_tol=0.01)
        assert poly[0] == (0.0, 0.0)
        assert poly[-1] == (20.0, 0.0)

    def test_mixed_path_only_subdivides_curves(self):
        # L-Q-L path: expect 2 (first L) + N_adaptive (Q) + 2 (last L), with
        # shared endpoints deduped.
        poly = P.flatten_path_adaptive("M0,0 L10,0 Q15,5 20,0 L30,0", flatness_tol=0.1)
        # Straight endpoints present and exact.
        assert (0.0, 0.0) in poly
        assert (10.0, 0.0) in poly
        assert (20.0, 0.0) in poly
        assert (30.0, 0.0) in poly
        # Short parabolic Q gets only a handful of samples at flatness 0.1.
        assert 5 <= len(poly) <= 30

    def test_max_depth_caps_recursion(self):
        # flatness_tol close to zero forces maximum subdivision; max_depth=3
        # caps at 2^3 = 8 sub-segments per curve segment → at most 9 points
        # plus whatever's in the Line pieces.
        poly = P.flatten_path_adaptive(
            "M0,0 Q10,20 20,0", flatness_tol=1e-9, max_depth=3,
        )
        # Exactly 2^3 + 1 = 9 points for the single Q at max depth.
        assert len(poly) == 9

    def test_rejects_non_positive_tolerance(self):
        with pytest.raises(ValueError):
            P.flatten_path_adaptive("M0,0 Q10,5 20,0", flatness_tol=0.0)
        with pytest.raises(ValueError):
            P.flatten_path_adaptive("M0,0 Q10,5 20,0", flatness_tol=-0.1)


class TestEdgePolylineAdaptiveMode:
    """`edge_polyline(..., flatness_tol=T)` switches to adaptive mode."""

    def test_flatness_tol_wins_over_samples_per_curve(self):
        # With flatness_tol set, samples_per_curve is ignored. Compare against
        # the fixed-N output on a curve where the two strategies differ.
        adaptive = P.edge_polyline(
            (0.0, 0.0), (20.0, 0.0), "M0,0 Q10,20 20,0",
            samples_per_curve=100,
            flatness_tol=0.1,
        )
        fixed = P.edge_polyline(
            (0.0, 0.0), (20.0, 0.0), "M0,0 Q10,20 20,0",
            samples_per_curve=100,
        )
        assert len(adaptive) < len(fixed)  # adaptive is much sparser at 0.1
        assert adaptive[0] == (0.0, 0.0)
        assert adaptive[-1] == (20.0, 0.0)

    def test_empty_path_unaffected(self):
        # No path_str → straight-line two-point polyline regardless of mode.
        poly = P.edge_polyline(
            (0.0, 0.0), (10.0, 0.0), None,
            flatness_tol=0.01,
        )
        assert poly == [(0.0, 0.0), (10.0, 0.0)]


class TestMetricsAdaptiveMode:
    """Smoke tests for flatness_fraction on the public metrics. The metric
    values should be close to the fixed-N defaults on well-sampled curves."""

    def _bezier_graph(self):
        import networkx as nx
        G = nx.Graph()
        G.add_node("a", x=0.0, y=0.0)
        G.add_node("b", x=20.0, y=0.0)
        G.add_edge("a", "b", polyline=True, path="M0,0 Q10,10 20,0")
        return G

    def test_edge_orthogonality_adaptive_matches_fixed_N(self):
        from geg import edge_orthogonality
        G = self._bezier_graph()
        fixed = edge_orthogonality(G, samples_per_curve=100)
        adaptive = edge_orthogonality(G, flatness_fraction=0.001)
        # Both measure the same curve; at tight tolerance and high N they
        # should agree to a few decimal places.
        assert adaptive == pytest.approx(fixed, abs=1e-3)

    def test_edge_crossings_adaptive_accepts_flatness_fraction(self):
        from geg import edge_crossings
        G = self._bezier_graph()
        score = edge_crossings(G, flatness_fraction=0.005)
        assert score == pytest.approx(1.0)  # single edge, no crossings

    def test_node_edge_occlusion_accepts_flatness_fraction(self):
        from geg import node_edge_occlusion
        G = self._bezier_graph()
        score = node_edge_occlusion(G, flatness_fraction=0.005)
        assert score == pytest.approx(1.0)  # 2 nodes, both endpoints

    def test_curves_promotion_accepts_flatness_fraction(self):
        from geg import curves_promotion
        G = self._bezier_graph()
        H_fixed = curves_promotion(G, samples_per_curve=100)
        H_adaptive = curves_promotion(G, flatness_fraction=0.005)
        # Adaptive should produce fewer intermediate nodes on this mild arc.
        assert H_adaptive.number_of_nodes() < H_fixed.number_of_nodes()
        # But both should still include the two original nodes.
        assert "a" in H_adaptive.nodes and "b" in H_adaptive.nodes
