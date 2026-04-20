"""Tests for geg.gabriel_ratio (edges + nodes variants).

Gabriel Ratio is excluded from the GD 2025 paper's canonical set
("not applicable for drawings with curves"); it remains in this library
as a non-canonical metric for straight-line drawings. An edge (u,v) is
*Gabriel* iff the open disk with diameter uv contains no other vertex.
"""

import math

import networkx as nx
import pytest

from geg import gabriel_ratio_edges, gabriel_ratio_nodes


def _layout(coords):
    G = nx.Graph()
    for n, (x, y) in coords.items():
        G.add_node(n, x=float(x), y=float(y))
    return G


class TestEdgesVariant:
    def test_no_edges_returns_one(self):
        G = _layout({"a": (0.0, 0.0)})
        assert gabriel_ratio_edges(G) == 1.0

    def test_isolated_edge_with_no_other_nodes(self):
        G = _layout({"a": (0.0, 0.0), "b": (1.0, 0.0)})
        G.add_edge("a", "b")
        # Vacuously Gabriel — no other nodes to violate the disk.
        assert gabriel_ratio_edges(G) == 1.0

    def test_equilateral_triangle_all_gabriel(self):
        """Equilateral triangle: at each edge's diameter disk the opposite
        vertex lies at distance sqrt(3)/2 from the midpoint, which exceeds
        the radius 1/2 → all three edges are Gabriel."""
        G = _layout({
            "a": (0.0, 0.0), "b": (1.0, 0.0),
            "c": (0.5, math.sqrt(3) / 2),
        })
        G.add_edges_from([("a", "b"), ("b", "c"), ("c", "a")])
        assert gabriel_ratio_edges(G) == 1.0

    def test_collinear_path(self):
        """Path a-b-c at (0,0), (1,0), (2,0). Each edge's disk has radius 0.5
        and the third node is at distance 1.5 from the midpoint → Gabriel."""
        G = _layout({"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (2.0, 0.0)})
        G.add_edges_from([("a", "b"), ("b", "c")])
        assert gabriel_ratio_edges(G) == 1.0

    def test_triangle_with_interior_violation(self):
        """Edge ab has midpoint (2, 0) and diameter 4 → disk has radius 2.
        Node c at (2, 0.1) is 0.1 from the midpoint, well inside the disk,
        so the edge is not Gabriel. With only this one edge, the ratio is
        (0 Gabriel edges) / (1 edge) = 0."""
        G = _layout({"a": (0.0, 0.0), "b": (4.0, 0.0), "c": (2.0, 0.1)})
        G.add_edge("a", "b")
        assert gabriel_ratio_edges(G) == 0.0

    def test_full_triangle_with_only_one_violating_edge(self):
        """Same positions as above but with all three edges present.
        Edges ac and bc have disks far too small to contain the opposite
        vertex; edge ab's disk contains c.  → 2/3."""
        G = _layout({"a": (0.0, 0.0), "b": (4.0, 0.0), "c": (2.0, 0.1)})
        G.add_edges_from([("a", "b"), ("a", "c"), ("b", "c")])
        assert gabriel_ratio_edges(G) == pytest.approx(2.0 / 3.0)


class TestNodesVariant:
    def test_two_node_case_returns_one(self):
        """num_nodes <= 2 → no 'other' nodes possible → 1.0."""
        G = _layout({"a": (0.0, 0.0), "b": (1.0, 0.0)})
        G.add_edge("a", "b")
        assert gabriel_ratio_nodes(G) == 1.0

    def test_no_violations_perfect_triangle(self):
        G = _layout({
            "a": (0.0, 0.0), "b": (1.0, 0.0),
            "c": (0.5, math.sqrt(3) / 2),
        })
        G.add_edges_from([("a", "b"), ("b", "c"), ("c", "a")])
        assert gabriel_ratio_nodes(G) == 1.0

    def test_triangle_with_violation_and_full_adjacency_discount(self):
        """Same violation as above but all three edges present. The single
        violation is (edge=ab, w=c) and c is adjacent to both a and b, so
        `possible` drops from 3*(3-2)=3 by 2 → 1. ratio = 1 - 1/1 = 0."""
        G = _layout({"a": (0.0, 0.0), "b": (4.0, 0.0), "c": (2.0, 0.1)})
        G.add_edges_from([("a", "b"), ("a", "c"), ("b", "c")])
        assert gabriel_ratio_nodes(G) == 0.0

    def test_single_edge_single_violator_no_adjacency(self):
        """Edge a-b, c inside disk, c not adjacent to either endpoint.
        num_edges=1, num_nodes=3, possible = 1, violations = 1 → 0."""
        G = _layout({"a": (0.0, 0.0), "b": (4.0, 0.0), "c": (2.0, 0.1)})
        G.add_edge("a", "b")
        assert gabriel_ratio_nodes(G) == 0.0


class TestSelfLoopsAndDuplicates:
    def test_self_loops_ignored(self):
        # Self-loops are explicitly skipped in both variants.
        G = _layout({"a": (0.0, 0.0), "b": (1.0, 0.0)})
        G.add_edge("a", "a")  # self-loop
        G.add_edge("a", "b")
        assert gabriel_ratio_edges(G) == 1.0
        assert gabriel_ratio_nodes(G) == 1.0
