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

    def test_s_curve_not_mistaken_for_flat(self):
        """Symmetric S-curves have their midpoint on the chord by symmetry,
        so a midpoint-only flatness test terminates after one check and
        misses the wild excursions at t=0.25 / t=0.75. The multi-probe
        test (0.25, 0.5, 0.75) catches this."""
        # Cubic S from (0, 0) to (100, 0): control points pull in opposite
        # directions. By symmetry, the curve midpoint is (50, 0) — exactly
        # on the chord — but t=0.25 and t=0.75 swing well off.
        poly = P.flatten_path_adaptive(
            "M0,0 C10,-60 90,60 100,0", flatness_tol=0.5,
        )
        assert len(poly) > 5  # must have subdivided at least twice

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

    def test_reverses_poly_when_path_authored_target_to_source(self):
        """NetworkX `G.edges(data=True)` on an undirected graph can yield
        (u, v) in the opposite order from how the edge was added, so the
        `source` passed to `edge_polyline` may correspond to the path's
        END rather than its start. edge_polyline must reverse the polyline
        in that case, otherwise poly[0] (path start) gets snapped to
        source and poly[-1] (path end) gets snapped to target even though
        the interior points were ordered for the opposite direction —
        yielding a polyline with a stray crossing segment."""
        # Path runs (10, 0) → (0, 10) via a quadratic. Caller passes
        # source=(0, 10) and target=(10, 0) — opposite direction.
        source = (0.0, 10.0)
        target = (10.0, 0.0)
        poly = P.edge_polyline(source, target, "M10,0 Q5,-5 0,10", samples_per_curve=20)
        # Endpoints must match source and target, not the other way around.
        assert poly[0] == source
        assert poly[-1] == target
        # Interior samples should trace smoothly from source toward target,
        # never jumping halfway across. The first interior sample's
        # distance to source must be small (first sample along the curve
        # near source), not large.
        assert len(poly) >= 3
        first_interior = poly[1]
        d_to_source = math.hypot(
            first_interior[0] - source[0], first_interior[1] - source[1],
        )
        d_to_target = math.hypot(
            first_interior[0] - target[0], first_interior[1] - target[1],
        )
        assert d_to_source < d_to_target, (
            f"first interior sample at {first_interior} is closer to target "
            f"{target} (d={d_to_target:.3f}) than to source {source} "
            f"(d={d_to_source:.3f}) — polyline was not reversed"
        )

    def test_same_direction_path_not_reversed(self):
        """Sanity: when the path is authored source → target (the normal
        case), edge_polyline must NOT reverse it."""
        source = (0.0, 0.0)
        target = (10.0, 0.0)
        poly = P.edge_polyline(source, target, "M0,0 Q5,5 10,0", samples_per_curve=10)
        assert poly[0] == source
        assert poly[-1] == target
        # Interior samples are on the true curve (y positive or similar),
        # not reversed to the mirror side.
        # For M0,0 Q5,5 10,0 (y>=0 throughout), all interior samples
        # should have y >= 0.
        for _, y in poly[1:-1]:
            assert y >= 0


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


class TestScaleInvariance:
    """Adaptive flattening scales tolerances proportionally to the node-bbox
    diagonal, so metric values must be identical on a graph regardless of
    whether its coordinates are in the 1e-3 or 1e+6 range. Also pin the
    flatness guarantee against extreme curve excursions where the curve
    peak is many orders of magnitude further from the chord than tol.
    """

    def _scaled_graph(self, k):
        """A small curved graph at scale `k`."""
        import networkx as nx
        G = nx.Graph()
        G.add_node("a", x=0.0, y=0.0)
        G.add_node("b", x=4.0 * k, y=0.0)
        G.add_node("c", x=2.0 * k, y=0.5 * k)
        G.add_node("d", x=2.0 * k, y=-0.5 * k)
        G.add_edge("a", "b", polyline=True,
                   path=f"M0,0 Q{2*k},{k} {4*k},0")
        G.add_edge("c", "d", path=f"M{2*k},{0.5*k} L{2*k},{-0.5*k}")
        return G

    def test_metric_values_identical_across_scales(self):
        """EO, EC, NEO on the same curved graph should return the same value
        whether coordinates are in tenths, ones, or millions."""
        from geg import edge_crossings, edge_orthogonality, node_edge_occlusion
        ref = None
        for k in [1e-3, 1.0, 1e3, 1e6]:
            G = self._scaled_graph(k)
            vals = (
                edge_orthogonality(G, flatness_fraction=0.005),
                edge_crossings(G, flatness_fraction=0.005),
                node_edge_occlusion(G, flatness_fraction=0.005),
            )
            if ref is None:
                ref = vals
            else:
                for name, a, b in zip(("EO", "EC", "NEO"), ref, vals):
                    assert a == pytest.approx(b, rel=1e-9, abs=1e-12), (
                        f"{name} drifted at scale k={k}: "
                        f"reference {a}, got {b}"
                    )

    def test_sample_count_invariant_across_scales(self):
        """Adaptive flattener produces the same number of sample points on
        geometrically-equivalent graphs at different scales."""
        ref_n = None
        for k in [1.0, 1e3, 1e6]:
            G = self._scaled_graph(k)
            tol = 0.005 * 4.0 * k  # flatness_fraction * node_diag
            poly = P.edge_polyline(
                source=(G.nodes["a"]["x"], G.nodes["a"]["y"]),
                target=(G.nodes["b"]["x"], G.nodes["b"]["y"]),
                path_str=G.edges["a", "b"]["path"],
                flatness_tol=tol,
            )
            if ref_n is None:
                ref_n = len(poly)
            else:
                assert len(poly) == ref_n, (
                    f"sample count drifted at scale k={k}: "
                    f"reference {ref_n}, got {len(poly)}"
                )

    def test_flatness_holds_under_extreme_curve_excursion(self):
        """Curve peak 10,000× the chord length, tolerance 0.5% of chord —
        adaptive subdivision must still keep every polyline sub-segment
        within `flatness_tol` of the true curve."""
        tol = 0.05  # 0.5% of node-bbox-diag=10
        path_str = "M0,0 Q5,100000 10,0"
        poly = P.flatten_path_adaptive(path_str, flatness_tol=tol)
        seg = list(P.parse_path(path_str))[0]
        max_dev = 0.0
        for k in range(2000):
            t = k / 1999
            p = seg.point(t)
            best = min(
                P._point_to_segment_distance(
                    p.real, p.imag, a[0], a[1], b[0], b[1]
                )
                for a, b in zip(poly, poly[1:])
            )
            max_dev = max(max_dev, best)
        assert max_dev <= tol + 1e-6, (
            f"flatness guarantee broken on extreme curve: peak y=100000, "
            f"tol={tol}, max_dev={max_dev}"
        )

    def test_degenerate_coincident_nodes_do_not_crash(self):
        """All nodes coincident → node-bbox diagonal = 0. The metrics must
        gracefully return a value (not crash), typically 1.0 for NEO/EC
        (no occlusion / no crossings detectable) and something shape-based
        for EO."""
        import networkx as nx
        from geg import edge_crossings, edge_orthogonality, node_edge_occlusion
        G = nx.Graph()
        G.add_node("a", x=5.0, y=5.0)
        G.add_node("b", x=5.0, y=5.0)
        G.add_edge("a", "b", polyline=True, path="M5,5 Q7,10 5,5")
        # Just assert they run without error and return finite floats.
        for metric in (edge_orthogonality, edge_crossings, node_edge_occlusion):
            val = metric(G, flatness_fraction=0.005)
            assert math.isfinite(val)
            assert 0.0 <= val <= 1.0
