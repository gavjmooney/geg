"""Tests for geg.edge_orthogonality.

Paper §3.2 eq. (5)-(6):
  EO(D) = 1 - (1/|E|) * sum_e δ_e
  δ_e   = sum_{j=1..k_e} min(θ_{e,j}, |90 - θ_{e,j}|, 180 - θ_{e,j}) / 45
                         * (ℓ_{e,j} / L(e))
where θ_{e,j} is the absolute angle in degrees between the j-th polyline
segment of edge e and the horizontal, ℓ_{e,j} is the segment length, and
L(e) = sum_j ℓ_{e,j}. Straight edges are the special case k_e = 1 with
weight 1.
"""

import math

import networkx as nx
import pytest

from geg import edge_orthogonality


def _layout(coords):
    G = nx.Graph()
    for n, (x, y) in coords.items():
        G.add_node(n, x=float(x), y=float(y))
    return G


class TestStraightEdges:
    def test_horizontal_edge_is_perfect(self):
        G = _layout({"a": (0.0, 0.0), "b": (5.0, 0.0)})
        G.add_edge("a", "b")
        assert edge_orthogonality(G) == pytest.approx(1.0)

    def test_vertical_edge_is_perfect(self):
        G = _layout({"a": (0.0, 0.0), "b": (0.0, 5.0)})
        G.add_edge("a", "b")
        assert edge_orthogonality(G) == pytest.approx(1.0)

    def test_45_degree_edge_is_zero(self):
        G = _layout({"a": (0.0, 0.0), "b": (1.0, 1.0)})
        G.add_edge("a", "b")
        assert edge_orthogonality(G) == pytest.approx(0.0)

    def test_135_degree_edge_is_zero(self):
        G = _layout({"a": (0.0, 0.0), "b": (-1.0, 1.0)})
        G.add_edge("a", "b")
        assert edge_orthogonality(G) == pytest.approx(0.0)

    def test_30_degree_edge(self):
        # tan(30°) = 1/sqrt(3).
        G = _layout({"a": (0.0, 0.0), "b": (math.sqrt(3), 1.0)})
        G.add_edge("a", "b")
        # δ = 30/45 = 2/3; EO = 1 - 2/3 = 1/3.
        assert edge_orthogonality(G) == pytest.approx(1.0 / 3.0)

    def test_unit_square_sides_perfect(self):
        G = _layout({
            "a": (0.0, 0.0), "b": (1.0, 0.0),
            "c": (1.0, 1.0), "d": (0.0, 1.0),
        })
        G.add_edges_from([("a", "b"), ("b", "c"), ("c", "d"), ("d", "a")])
        assert edge_orthogonality(G) == pytest.approx(1.0)

    def test_mix_of_horizontal_and_diagonal(self):
        # Two edges: one horizontal (δ=0), one at 45° (δ=1). EO = 1 - 0.5 = 0.5.
        G = _layout({
            "a": (0.0, 0.0), "b": (1.0, 0.0),
            "c": (0.0, 0.0), "d": (1.0, 1.0),
        })
        G.add_edge("a", "b")
        G.add_edge("c", "d")
        # Two edges share coords; that's OK for EO.
        assert edge_orthogonality(G) == pytest.approx(0.5)


class TestCurvedEdges:
    def test_polyline_two_orthogonal_segments(self):
        # Edge a-b with a polyline (0,0)→(1,0)→(1,1): both segments orthogonal.
        G = _layout({"a": (0.0, 0.0), "b": (1.0, 1.0)})
        G.add_edge("a", "b", polyline=True, path="M0,0 L1,0 L1,1")
        assert edge_orthogonality(G) == pytest.approx(1.0)

    def test_polyline_one_orthogonal_one_diagonal(self):
        """Polyline (0,0)→(1,0)→(2,1):
          seg 1: horizontal, length 1 → deviation 0
          seg 2: 45° diagonal, length sqrt(2) → deviation 1
        total length 1 + sqrt(2); δ_e = 0 + 1 * sqrt(2)/(1+sqrt(2)).
        """
        G = _layout({"a": (0.0, 0.0), "b": (2.0, 1.0)})
        G.add_edge("a", "b", polyline=True, path="M0,0 L1,0 L2,1")
        expected_delta = math.sqrt(2) / (1.0 + math.sqrt(2))
        expected_eo = 1.0 - expected_delta
        assert edge_orthogonality(G) == pytest.approx(expected_eo, rel=1e-6)


class TestDegenerate:
    def test_no_edges_returns_one(self):
        """Vacuously orthogonal (no edges to deviate)."""
        G = _layout({"a": (0.0, 0.0)})
        assert edge_orthogonality(G) == 1.0


class TestInvariants:
    def test_translation_invariant(self):
        coords = {"a": (0.0, 0.0), "b": (math.sqrt(3), 1.0)}
        G1 = _layout(coords)
        G1.add_edge("a", "b")
        G2 = _layout({n: (x + 100, y - 500) for n, (x, y) in coords.items()})
        G2.add_edge("a", "b")
        assert edge_orthogonality(G1) == pytest.approx(edge_orthogonality(G2))

    def test_uniform_scale_invariant(self):
        coords = {"a": (0.0, 0.0), "b": (math.sqrt(3), 1.0)}
        G1 = _layout(coords)
        G1.add_edge("a", "b")
        G2 = _layout({n: (x * 42.0, y * 42.0) for n, (x, y) in coords.items()})
        G2.add_edge("a", "b")
        assert edge_orthogonality(G1) == pytest.approx(edge_orthogonality(G2))

    # Note on rotation invariance: EO measures how close each edge is to
    # the horizontal or vertical axis (deviation normalised by 45°). It is
    # *not* invariant under arbitrary rotations — rotating by e.g. 30°
    # turns a perfect horizontal edge into a 30° edge, whose deviation is
    # 30/45. Only 90° rotations preserve the metric (horizontal ↔ vertical
    # and both count as orthogonal). Tested directly:

    def test_90_degree_rotation_gives_same_value(self):
        """Rotating 90° swaps horizontal ↔ vertical; both are orthogonal,
        so the metric is invariant under 90° rotations."""
        coords = {"a": (0.0, 0.0), "b": (math.sqrt(3), 1.0)}
        G1 = _layout(coords)
        G1.add_edge("a", "b")
        # Rotate 90° about origin: (x, y) → (-y, x).
        G2 = _layout({n: (-y, x) for n, (x, y) in coords.items()})
        G2.add_edge("a", "b")
        assert edge_orthogonality(G1) == pytest.approx(edge_orthogonality(G2))
