import math

import pytest

from geg import _geometry as G


class TestDistance:
    def test_zero(self):
        assert G.distance((0.0, 0.0), (0.0, 0.0)) == 0.0

    def test_horizontal(self):
        assert G.distance((0.0, 0.0), (3.0, 0.0)) == 3.0

    def test_vertical(self):
        assert G.distance((1.0, 2.0), (1.0, 6.0)) == 4.0

    def test_3_4_5(self):
        assert G.distance((0.0, 0.0), (3.0, 4.0)) == 5.0

    def test_negative_coords(self):
        assert G.distance((-1.0, -1.0), (2.0, 3.0)) == 5.0

    def test_symmetric(self):
        a, b = (1.3, -2.7), (4.8, 9.1)
        assert G.distance(a, b) == pytest.approx(G.distance(b, a))


class TestSquaredDistance:
    def test_zero(self):
        assert G.squared_distance((0.0, 0.0), (0.0, 0.0)) == 0.0

    def test_3_4_5(self):
        assert G.squared_distance((0.0, 0.0), (3.0, 4.0)) == 25.0

    def test_matches_distance_squared(self):
        a, b = (1.3, -2.7), (4.8, 9.1)
        assert G.squared_distance(a, b) == pytest.approx(G.distance(a, b) ** 2)


class TestAngleBetween:
    # Returns the unsigned angle between two 2D vectors in radians, in [0, pi].

    def test_same_direction(self):
        assert G.angle_between((1.0, 0.0), (2.0, 0.0)) == pytest.approx(0.0)

    def test_perpendicular(self):
        assert G.angle_between((1.0, 0.0), (0.0, 1.0)) == pytest.approx(math.pi / 2)

    def test_perpendicular_negative_y(self):
        assert G.angle_between((1.0, 0.0), (0.0, -1.0)) == pytest.approx(math.pi / 2)

    def test_opposite(self):
        assert G.angle_between((1.0, 0.0), (-1.0, 0.0)) == pytest.approx(math.pi)

    def test_45_degrees(self):
        assert G.angle_between((1.0, 0.0), (1.0, 1.0)) == pytest.approx(math.pi / 4)

    def test_zero_vector_returns_nan_or_raises(self):
        # A zero-magnitude vector has undefined angle; either NaN or ValueError is acceptable.
        with pytest.raises((ValueError, ZeroDivisionError)):
            G.angle_between((0.0, 0.0), (1.0, 0.0))


class TestAcuteAngleBetween:
    # Returns the acute (non-reflex, folded into [0, pi/2]) angle between two vectors.

    def test_same_direction(self):
        assert G.acute_angle_between((1.0, 0.0), (1.0, 0.0)) == pytest.approx(0.0)

    def test_opposite_returns_zero(self):
        # Opposite vectors are folded to 0.
        assert G.acute_angle_between((1.0, 0.0), (-1.0, 0.0)) == pytest.approx(0.0)

    def test_perpendicular(self):
        assert G.acute_angle_between((1.0, 0.0), (0.0, 1.0)) == pytest.approx(math.pi / 2)

    def test_135_degrees_folds_to_45(self):
        # angle_between is 135°; acute folds to 45°.
        assert G.acute_angle_between((1.0, 0.0), (-1.0, 1.0)) == pytest.approx(math.pi / 4)


class TestBoundingBox:
    def test_single_point(self):
        assert G.bounding_box([(2.0, 3.0)]) == (2.0, 3.0, 2.0, 3.0)

    def test_two_points(self):
        assert G.bounding_box([(0.0, 0.0), (4.0, 3.0)]) == (0.0, 0.0, 4.0, 3.0)

    def test_negative_coords(self):
        pts = [(-5.0, -2.0), (0.0, 0.0), (3.0, 7.0)]
        assert G.bounding_box(pts) == (-5.0, -2.0, 3.0, 7.0)

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            G.bounding_box([])


class TestBBoxesIntersect:
    def test_overlap_clear(self):
        assert G.bboxes_intersect((0, 0), (2, 2), (1, 1), (3, 3)) is True

    def test_touching_corner(self):
        assert G.bboxes_intersect((0, 0), (1, 1), (1, 1), (2, 2)) is True

    def test_separated_x(self):
        assert G.bboxes_intersect((0, 0), (1, 1), (2, 0), (3, 1)) is False

    def test_separated_y(self):
        assert G.bboxes_intersect((0, 0), (1, 1), (0, 2), (1, 3)) is False

    def test_one_inside_other(self):
        assert G.bboxes_intersect((0, 0), (10, 10), (3, 3), (4, 4)) is True

    def test_horizontal_vs_vertical_cross(self):
        # Horizontal segment through a vertical segment's x-range.
        assert G.bboxes_intersect((0, 1), (4, 1), (2, 0), (2, 2)) is True


class TestSegmentIntersection:
    def test_clear_cross_at_origin(self):
        # Two segments crossing at (0, 0), angle 90°.
        hit = G.segment_intersection((-1, 0), (1, 0), (0, -1), (0, 1))
        assert hit is not None
        (x, y), angle = hit
        assert (x, y) == pytest.approx((0.0, 0.0))
        assert angle == pytest.approx(90.0)

    def test_45_degree_cross(self):
        # y=x vs. horizontal through origin → 45° crossing.
        hit = G.segment_intersection((-1, -1), (1, 1), (-1, 0), (1, 0))
        assert hit is not None
        _, angle = hit
        assert angle == pytest.approx(45.0)

    def test_parallel_no_intersection(self):
        assert G.segment_intersection((0, 0), (1, 0), (0, 1), (1, 1)) is None

    def test_collinear_no_intersection(self):
        assert G.segment_intersection((0, 0), (1, 0), (2, 0), (3, 0)) is None

    def test_t_endpoint_excluded(self):
        # Shared endpoint at (1, 0) — excluded by interior-only intersection rule.
        assert G.segment_intersection((0, 0), (1, 0), (1, 0), (2, 1)) is None

    def test_u_endpoint_excluded(self):
        # Second segment touches first segment only at its own endpoint — excluded.
        assert G.segment_intersection((0, 0), (2, 0), (1, -1), (1, 0)) is None

    def test_no_intersection_disjoint(self):
        assert G.segment_intersection((0, 0), (1, 0), (2, 2), (3, 3)) is None

    def test_near_parallel_tol(self):
        # Very nearly parallel — within default tol — returns None.
        assert G.segment_intersection((0, 0), (1, 0), (0, 1e-12), (1, 1e-12)) is None
