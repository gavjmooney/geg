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
    """The nodes variant counts (edge, violator) pairs and discounts the
    denominator for adjacency between the violator and the edge's endpoints.
    The two violation tests below intentionally return the same score (0.0)
    while exercising opposite branches of the discount formula — see their
    docstrings.
    """

    def test_two_node_case_returns_one(self):
        """num_nodes <= 2 → early-return branch (no 'other' nodes possible)."""
        G = _layout({"a": (0.0, 0.0), "b": (1.0, 0.0)})
        G.add_edge("a", "b")
        assert gabriel_ratio_nodes(G) == 1.0

    def test_violation_with_no_adjacency_discount(self):
        """*No-discount* branch. Isolated edge a-b with one violator c that
        is NOT incident to either endpoint:
            num_edges = 1, num_nodes = 3
            possible_non_conforming = 1 * (3 - 2) = 1   (no subtraction)
            num_non_conforming      = 1
            ratio                   = 1 - 1/1 = 0
        Distinct from `test_violation_with_full_adjacency_discount`: same
        score, different code path (the discount loop runs zero times)."""
        G = _layout({"a": (0.0, 0.0), "b": (4.0, 0.0), "c": (2.0, 0.1)})
        G.add_edge("a", "b")
        assert gabriel_ratio_nodes(G) == 0.0

    def test_violation_with_full_adjacency_discount(self):
        """*Full-discount* branch. Triangle a-b-c with violator c inside the
        ab disk, and c IS adjacent to both endpoints:
            num_edges = 3, num_nodes = 3
            possible_non_conforming = 3*(3-2) = 3, then -1 for c-a and -1 for
                                      c-b incidences → 1
            num_non_conforming      = 1   (only ab is violated)
            ratio                   = 1 - 1/1 = 0
        Distinct from `test_violation_with_no_adjacency_discount`: same
        score, different code path (full discount saturates the denominator)."""
        G = _layout({"a": (0.0, 0.0), "b": (4.0, 0.0), "c": (2.0, 0.1)})
        G.add_edges_from([("a", "b"), ("a", "c"), ("b", "c")])
        assert gabriel_ratio_nodes(G) == 0.0

    def test_intermediate_value_no_discount(self):
        """Non-trivial nodes-variant ratio (not 0 or 1). Single edge a-b
        with one violator (c) and one non-violator (d, far away):
            num_edges = 1, num_nodes = 4
            possible_non_conforming = 1 * (4 - 2) = 2
            num_non_conforming      = 1
            ratio                   = 1 - 1/2 = 0.5
        Without this case, both the no-discount and full-discount tests pin
        the ratio at exactly 0, so a regression that always returned 0
        would still pass the suite."""
        G = _layout({
            "a": (0.0, 0.0),
            "b": (4.0, 0.0),
            "c": (2.0, 0.1),
            "d": (0.0, 50.0),
        })
        G.add_edge("a", "b")
        assert gabriel_ratio_nodes(G) == pytest.approx(0.5)


class TestSelfLoopsAndDuplicates:
    def test_self_loops_ignored(self):
        # Self-loops are explicitly skipped in both variants.
        G = _layout({"a": (0.0, 0.0), "b": (1.0, 0.0)})
        G.add_edge("a", "a")  # self-loop
        G.add_edge("a", "b")
        assert gabriel_ratio_edges(G) == 1.0
        assert gabriel_ratio_nodes(G) == 1.0
