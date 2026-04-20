"""Tests for geg.graph_properties.

Pins expected values for each property on small, hand-analysable graphs.
Distance-based properties (diameter / radius / avg_shortest_path_length)
mirror the kruskal_stress / neighbourhood_preservation disconnected-graph
logic: per-component weighted sum by component node count, singletons
skipped, NaN if every component is a singleton.
"""

import math

import networkx as nx
import pytest

from geg import graph_properties as gp


# ---------- basic counts & flags ----------

class TestBasicCounts:
    def test_empty(self):
        G = nx.Graph()
        assert gp.n_nodes(G) == 0
        assert gp.n_edges(G) == 0
        assert gp.density(G) == 0.0
        assert gp.is_connected(G) is False

    def test_k4(self):
        G = nx.complete_graph(4)
        assert gp.n_nodes(G) == 4
        assert gp.n_edges(G) == 6
        assert gp.density(G) == pytest.approx(1.0)
        assert gp.is_connected(G) is True

    def test_self_loops_counted(self):
        G = nx.Graph()
        G.add_edge(0, 0)
        G.add_edge(1, 2)
        assert gp.n_self_loops(G) == 1

    def test_directed_flag(self):
        assert gp.is_directed(nx.Graph()) is False
        assert gp.is_directed(nx.DiGraph()) is True

    def test_multigraph_flag(self):
        assert gp.is_multigraph(nx.Graph()) is False
        assert gp.is_multigraph(nx.MultiGraph()) is True

    def test_components_disconnected(self):
        G = nx.Graph()
        G.add_edges_from([(0, 1), (2, 3), (4, 5)])  # three edges, three CCs
        assert gp.n_connected_components(G) == 3
        assert gp.is_connected(G) is False


# ---------- degree statistics ----------

class TestDegree:
    def test_path_p4(self):
        G = nx.path_graph(4)
        assert gp.min_degree(G) == 1
        assert gp.max_degree(G) == 2
        assert gp.mean_degree(G) == pytest.approx(1.5)
        assert gp.degree_std(G) == pytest.approx(math.sqrt(0.25))

    def test_empty_returns_zero(self):
        G = nx.Graph()
        assert gp.min_degree(G) == 0
        assert gp.max_degree(G) == 0
        assert gp.mean_degree(G) == 0.0
        assert gp.degree_std(G) == 0.0

    def test_star_has_high_max_low_min(self):
        G = nx.star_graph(5)  # centre + 5 leaves
        assert gp.min_degree(G) == 1
        assert gp.max_degree(G) == 5


# ---------- structural classes ----------

class TestStructural:
    def test_path_is_tree(self):
        assert gp.is_tree(nx.path_graph(4)) is True

    def test_cycle_is_not_tree(self):
        assert gp.is_tree(nx.cycle_graph(4)) is False

    def test_forest_two_components(self):
        G = nx.Graph()
        G.add_edges_from([(0, 1), (2, 3)])
        assert gp.is_forest(G) is True
        assert gp.is_tree(G) is False  # two components, not a single tree

    def test_bipartite_cycle_even(self):
        assert gp.is_bipartite(nx.cycle_graph(4)) is True
        assert gp.is_bipartite(nx.cycle_graph(5)) is False

    def test_planar(self):
        assert gp.is_planar(nx.complete_graph(4)) is True
        assert gp.is_planar(nx.complete_graph(5)) is False  # K5 nonplanar
        assert gp.is_planar(nx.complete_bipartite_graph(3, 3)) is False  # K_{3,3}

    def test_is_dag_only_directed(self):
        G = nx.DiGraph()
        G.add_edges_from([(0, 1), (1, 2)])
        assert gp.is_dag(G) is True

        G.add_edge(2, 0)  # cycle
        assert gp.is_dag(G) is False

        assert gp.is_dag(nx.Graph([(0, 1)])) is False  # undirected → False

    def test_is_regular(self):
        assert gp.is_regular(nx.cycle_graph(5)) is True   # every node degree 2
        assert gp.is_regular(nx.path_graph(4)) is False
        assert gp.is_regular(nx.Graph()) is True          # vacuous

    def test_is_eulerian(self):
        assert gp.is_eulerian(nx.cycle_graph(4)) is True  # 2-regular closed
        assert gp.is_eulerian(nx.path_graph(3)) is False  # odd-degree endpoints


# ---------- distances (per-component weighted sum) ----------

class TestDistances:
    def test_path_p4_diameter_radius(self):
        G = nx.path_graph(4)
        assert gp.diameter(G) == pytest.approx(3)
        assert gp.radius(G) == pytest.approx(2)
        # ASPL of P4 = 10/6.
        assert gp.avg_shortest_path_length(G) == pytest.approx(10 / 6)

    def test_k4_diameter_1(self):
        G = nx.complete_graph(4)
        assert gp.diameter(G) == pytest.approx(1)
        assert gp.radius(G) == pytest.approx(1)

    def test_disconnected_weighted_sum(self):
        # K3 (diam 1, 3 nodes) and P3 (diam 2, 3 nodes).
        G = nx.disjoint_union(nx.complete_graph(3), nx.path_graph(3))
        # Weighted by node count: (1*3 + 2*3) / (3 + 3) = 1.5.
        assert gp.diameter(G) == pytest.approx(1.5)

    def test_all_singletons_returns_nan(self):
        G = nx.Graph()
        G.add_nodes_from([0, 1, 2])  # no edges → three singletons
        assert math.isnan(gp.diameter(G))
        assert math.isnan(gp.radius(G))
        assert math.isnan(gp.avg_shortest_path_length(G))

    def test_singletons_are_skipped_not_crashed(self):
        # Single K3 + isolated node; singleton contributes 0 weight.
        G = nx.complete_graph(3)
        G.add_node(99)
        assert gp.diameter(G) == pytest.approx(1)

    def test_directed_treated_as_undirected(self):
        """Distance properties use the undirected CC decomposition just like
        kruskal_stress does."""
        G = nx.DiGraph()
        G.add_edges_from([(0, 1), (1, 2)])  # undirected path
        # Sinks would break a naive directed all-pairs.
        assert gp.diameter(G) == pytest.approx(2)


# ---------- clustering / triangles ----------

class TestClustering:
    def test_triangle_count_on_k4(self):
        # K4 has C(4,3) = 4 triangles.
        assert gp.n_triangles(nx.complete_graph(4)) == 4

    def test_triangle_count_on_path(self):
        assert gp.n_triangles(nx.path_graph(4)) == 0

    def test_average_clustering_complete(self):
        # Kn has clustering coefficient 1 at every node.
        assert gp.average_clustering(nx.complete_graph(5)) == pytest.approx(1.0)

    def test_average_clustering_tree(self):
        assert gp.average_clustering(nx.path_graph(5)) == pytest.approx(0.0)

    def test_transitivity_complete(self):
        assert gp.transitivity(nx.complete_graph(5)) == pytest.approx(1.0)


# ---------- assortativity ----------

class TestAssortativity:
    def test_star_is_disassortative(self):
        # Star: hub-leaf edges all connect high-degree to low-degree nodes.
        r = gp.degree_assortativity(nx.star_graph(5))
        assert r < 0

    def test_regular_graph_is_nan(self):
        # Every edge has the same degree pair → undefined correlation.
        r = gp.degree_assortativity(nx.cycle_graph(5))
        assert math.isnan(r)


# ---------- compute_properties ----------

class TestComputeProperties:
    def test_returns_all_keys(self):
        G = nx.path_graph(4)
        result = gp.compute_properties(G)
        assert set(result.keys()) == set(gp.PROPERTY_NAMES)

    def test_types_are_reasonable(self):
        G = nx.complete_graph(4)
        result = gp.compute_properties(G)
        assert isinstance(result["n_nodes"], int)
        assert isinstance(result["density"], float)
        assert isinstance(result["is_tree"], bool)
        assert isinstance(result["is_planar"], bool)

    def test_failure_becomes_nan(self, monkeypatch):
        """A broken property must not kill the rest of the row."""
        def bad(G):
            raise RuntimeError("boom")
        monkeypatch.setattr(gp, "diameter", bad)
        result = gp.compute_properties(nx.path_graph(4))
        assert math.isnan(result["diameter"])
        # Other properties still computed.
        assert result["n_nodes"] == 4

    def test_exported_from_top_level(self):
        import geg
        assert geg.compute_properties is gp.compute_properties
        assert geg.graph_properties is gp


class TestApspSharing:
    """Distance properties accept a precomputed APSP dict shared with
    kruskal_stress. When passed, they use it instead of running their own
    BFS — values must be identical to the unshared path."""

    def test_diameter_with_apsp_matches_without(self):
        G = nx.path_graph(5)
        apsp = gp.compute_apsp(G)
        assert gp.diameter(G, apsp=apsp) == pytest.approx(gp.diameter(G))

    def test_radius_with_apsp_matches_without(self):
        G = nx.cycle_graph(7)
        apsp = gp.compute_apsp(G)
        assert gp.radius(G, apsp=apsp) == pytest.approx(gp.radius(G))

    def test_avg_spl_with_apsp_matches_without(self):
        G = nx.complete_graph(5)
        apsp = gp.compute_apsp(G)
        assert gp.avg_shortest_path_length(G, apsp=apsp) == pytest.approx(
            gp.avg_shortest_path_length(G)
        )

    def test_apsp_shared_across_distance_props(self, monkeypatch):
        """Passing one precomputed APSP to all three distance properties
        avoids re-running compute_apsp."""
        calls = {"n": 0}
        original = gp.compute_apsp

        def counting(G, *a, **kw):
            calls["n"] += 1
            return original(G, *a, **kw)

        monkeypatch.setattr(gp, "compute_apsp", counting)

        G = nx.path_graph(6)
        apsp = gp.compute_apsp(G)
        gp.diameter(G, apsp=apsp)
        gp.radius(G, apsp=apsp)
        gp.avg_shortest_path_length(G, apsp=apsp)
        gp.compute_properties(G, apsp=apsp)
        # 1 call total — the one we made ourselves above.
        assert calls["n"] == 1

    def test_disconnected_apsp_sum_matches(self):
        """Disconnected graph: apsp-based weighted sum must match the
        networkx per-component route exactly."""
        G = nx.disjoint_union(nx.complete_graph(4), nx.path_graph(3))
        apsp = gp.compute_apsp(G)
        assert gp.diameter(G, apsp=apsp) == pytest.approx(gp.diameter(G))
        assert gp.radius(G, apsp=apsp) == pytest.approx(gp.radius(G))
        assert gp.avg_shortest_path_length(G, apsp=apsp) == pytest.approx(
            gp.avg_shortest_path_length(G)
        )

    def test_kruskal_stress_accepts_apsp(self):
        """kruskal_stress must accept the same APSP dict and produce the
        same value as without."""
        import geg as geg_pkg
        G = nx.path_graph(5)
        for n, (x, y) in {0: (0, 0), 1: (1, 0), 2: (2, 0), 3: (3, 0), 4: (4, 0)}.items():
            G.nodes[n]["x"] = float(x)
            G.nodes[n]["y"] = float(y)
        apsp = gp.compute_apsp(G)
        assert geg_pkg.kruskal_stress(G, apsp=apsp) == pytest.approx(
            geg_pkg.kruskal_stress(G)
        )
