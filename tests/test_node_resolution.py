"""Tests for geg.node_resolution.

Paper §3.2 eq. (9): NR(D) = min ||u-v|| / max ||u-v|| over all pairs.
"""

import math

import networkx as nx
import pytest

from geg import node_resolution


def _layout(coords):
    G = nx.Graph()
    for n, (x, y) in coords.items():
        G.add_node(n, x=float(x), y=float(y))
    return G


class TestDegenerate:
    def test_single_node(self):
        G = _layout({"a": (0.0, 0.0)})
        assert node_resolution(G) == 1.0

    def test_two_nodes(self):
        G = _layout({"a": (0.0, 0.0), "b": (1.0, 0.0)})
        assert node_resolution(G) == 1.0

    def test_all_coincident(self):
        G = _layout({"a": (0.0, 0.0), "b": (0.0, 0.0), "c": (0.0, 0.0)})
        assert node_resolution(G) == 0.0


class TestPerfectResolution:
    def test_equilateral_triangle(self):
        G = _layout({
            "a": (0.0, 0.0),
            "b": (1.0, 0.0),
            "c": (0.5, math.sqrt(3) / 2),
        })
        assert node_resolution(G) == pytest.approx(1.0)


class TestKnownRatios:
    def test_right_triangle_3_4_5(self):
        # min = 3, max = 5 → 3/5.
        G = _layout({"a": (0.0, 0.0), "b": (3.0, 0.0), "c": (0.0, 4.0)})
        assert node_resolution(G) == pytest.approx(3.0 / 5.0)

    def test_unit_square(self):
        # Sides = 1, diagonals = sqrt(2).
        G = _layout({
            "a": (0.0, 0.0), "b": (1.0, 0.0),
            "c": (1.0, 1.0), "d": (0.0, 1.0),
        })
        assert node_resolution(G) == pytest.approx(1.0 / math.sqrt(2))

    def test_collinear_0_1_3(self):
        # Pairwise distances = {1, 2, 3}. NR = 1/3.
        G = _layout({"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (3.0, 0.0)})
        assert node_resolution(G) == pytest.approx(1.0 / 3.0)


class TestInvariants:
    def test_ignores_edges(self):
        # NR is a pure node-position metric; adding/removing edges does nothing.
        G1 = _layout({"a": (0.0, 0.0), "b": (3.0, 0.0), "c": (0.0, 4.0)})
        G2 = _layout({"a": (0.0, 0.0), "b": (3.0, 0.0), "c": (0.0, 4.0)})
        G2.add_edges_from([("a", "b"), ("b", "c")])
        assert node_resolution(G1) == pytest.approx(node_resolution(G2))

    def test_uniform_scale_invariant(self):
        coords = {"a": (0.0, 0.0), "b": (3.0, 0.0), "c": (0.0, 4.0)}
        G1 = _layout(coords)
        G2 = _layout({n: (x * 42.7, y * 42.7) for n, (x, y) in coords.items()})
        assert node_resolution(G1) == pytest.approx(node_resolution(G2))

    def test_rotation_invariant(self):
        # Rotate 3-4-5 triangle by 37° about origin.
        theta = math.radians(37.0)
        c, s = math.cos(theta), math.sin(theta)
        coords = {"a": (0.0, 0.0), "b": (3.0, 0.0), "c": (0.0, 4.0)}
        rotated = {n: (x * c - y * s, x * s + y * c) for n, (x, y) in coords.items()}
        G1 = _layout(coords)
        G2 = _layout(rotated)
        assert node_resolution(G1) == pytest.approx(node_resolution(G2))
