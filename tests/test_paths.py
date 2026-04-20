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
