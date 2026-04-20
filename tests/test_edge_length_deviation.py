"""Tests for geg.edge_length_deviation.

Paper §3.2 eq. (4):
  ELD(D) = 1 / (1 + (1/|E|) * sum_e |L(e) - L_ideal| / L_ideal)
with L_ideal = (1/|E|) * sum_e L(e).
"""

import math

import networkx as nx
import pytest

from geg import edge_length_deviation


def _layout(coords):
    G = nx.Graph()
    for n, (x, y) in coords.items():
        G.add_node(n, x=float(x), y=float(y))
    return G


class TestPerfectUniformity:
    """Every edge has the same length, so L_e = L_ideal for all e; each
    |L_e - L_ideal| / L_ideal term is 0 and ELD = 1/(1+0) = 1."""

    def test_equilateral_triangle(self):
        # Three sides all of length 1 (equilateral) → no deviation.
        G = _layout({
            "a": (0.0, 0.0), "b": (1.0, 0.0),
            "c": (0.5, math.sqrt(3) / 2),
        })
        G.add_edges_from([("a", "b"), ("b", "c"), ("c", "a")])
        assert edge_length_deviation(G) == pytest.approx(1.0)

    def test_unit_square_only_sides(self):
        # Four sides all of length 1; diagonals not included.
        G = _layout({
            "a": (0.0, 0.0), "b": (1.0, 0.0),
            "c": (1.0, 1.0), "d": (0.0, 1.0),
        })
        G.add_edges_from([("a", "b"), ("b", "c"), ("c", "d"), ("d", "a")])
        assert edge_length_deviation(G) == pytest.approx(1.0)


class TestKnownDeviations:
    def test_two_edge_path_lengths_1_and_2(self):
        """a-b-c at (0,0), (1,0), (3,0) → lengths 1 and 2.
        L_ideal = 1.5.
        rel dev per edge = 0.5/1.5 = 1/3. sum = 2/3. avg = 1/3.
        ELD = 1 / (1 + 1/3) = 3/4.
        """
        G = _layout({"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (3.0, 0.0)})
        G.add_edges_from([("a", "b"), ("b", "c")])
        assert edge_length_deviation(G) == pytest.approx(0.75)

    def test_explicit_ideal(self):
        """Triangle with all sides = 1, but user-supplied ideal = 2.
        rel dev per edge = |1 - 2| / 2 = 0.5. avg = 0.5.
        ELD = 1 / (1 + 0.5) = 2/3.
        """
        G = _layout({
            "a": (0.0, 0.0), "b": (1.0, 0.0),
            "c": (0.5, math.sqrt(3) / 2),
        })
        G.add_edges_from([("a", "b"), ("b", "c"), ("c", "a")])
        assert edge_length_deviation(G, ideal=2.0) == pytest.approx(2.0 / 3.0)


class TestCurvedEdges:
    def test_polyline_uses_arc_length(self):
        """Edge a-b where a=(0,0), b=(4,0). A polyline that goes (0,0)-(2,3)-(4,0)
        has total length 2*sqrt(13) ≈ 7.211. One other edge is a straight unit
        edge. Expected L_ideal = (7.211 + 1)/2 ≈ 4.106, from which ELD follows.
        """
        G = _layout({
            "a": (0.0, 0.0), "b": (4.0, 0.0),
            "c": (5.0, 0.0), "d": (6.0, 0.0),
        })
        G.add_edge("a", "b", polyline=True, path="M0,0 L2,3 L4,0")
        G.add_edge("c", "d")  # straight unit edge

        L1 = 2 * math.sqrt(13)  # polyline
        L2 = 1.0
        ideal = (L1 + L2) / 2
        avg_dev = (abs(L1 - ideal) + abs(L2 - ideal)) / (2 * ideal)
        expected = 1.0 / (1.0 + avg_dev)
        assert edge_length_deviation(G) == pytest.approx(expected, rel=1e-6)


class TestDegenerate:
    def test_no_edges_returns_one(self):
        """Vacuously perfect: no edges → no deviation → ELD = 1."""
        G = _layout({"a": (0.0, 0.0), "b": (1.0, 0.0)})
        assert edge_length_deviation(G) == 1.0

    def test_all_zero_length_edges_returns_one(self):
        """All edges have length 0 → uniform → ELD = 1 (currently divides by 0)."""
        G = _layout({"a": (0.0, 0.0), "b": (0.0, 0.0), "c": (0.0, 0.0)})
        G.add_edges_from([("a", "b"), ("b", "c")])
        assert edge_length_deviation(G) == pytest.approx(1.0)


class TestInvariants:
    """ELD compares edge lengths L(e) to the per-graph mean L_ideal via
    relative deviations |L(e) - L_ideal| / L_ideal. Lengths are invariant
    under translation and arbitrary rotation; uniform scaling multiplies
    every L by the same constant so the ratios are unchanged."""

    def test_translation_invariant(self):
        coords = {"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (3.0, 0.0)}
        G1 = _layout(coords)
        G1.add_edges_from([("a", "b"), ("b", "c")])
        G2 = _layout({n: (x + 100.0, y - 37.0) for n, (x, y) in coords.items()})
        G2.add_edges_from([("a", "b"), ("b", "c")])
        assert edge_length_deviation(G1) == pytest.approx(edge_length_deviation(G2))

    def test_uniform_scale_invariant(self):
        coords = {"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (3.0, 0.0)}
        G1 = _layout(coords)
        G1.add_edges_from([("a", "b"), ("b", "c")])
        G2 = _layout({n: (x * 42.0, y * 42.0) for n, (x, y) in coords.items()})
        G2.add_edges_from([("a", "b"), ("b", "c")])
        assert edge_length_deviation(G1) == pytest.approx(edge_length_deviation(G2))

    def test_arbitrary_rotation_invariant(self):
        theta = math.radians(37.0)
        c, s = math.cos(theta), math.sin(theta)
        coords = {"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (3.0, 0.0)}
        G1 = _layout(coords)
        G1.add_edges_from([("a", "b"), ("b", "c")])
        G2 = _layout({n: (x * c - y * s, x * s + y * c) for n, (x, y) in coords.items()})
        G2.add_edges_from([("a", "b"), ("b", "c")])
        assert edge_length_deviation(G1) == pytest.approx(edge_length_deviation(G2))
