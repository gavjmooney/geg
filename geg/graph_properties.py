"""Graph properties — topological descriptors independent of the layout.

Unlike the layout metrics in this package, these functions care only about
the node / edge sets and directed-vs-undirected structure. Every function
takes a NetworkX graph and returns a single value (number or boolean).

Distance-based properties (`diameter`, `radius`, `avg_shortest_path_length`)
handle disconnected graphs the same way `kruskal_stress` and
`neighbourhood_preservation` do: compute per connected component and
aggregate as a weighted sum by component node count. Singleton components
contribute zero weight. An empty graph, or one that is entirely singletons,
returns NaN.

`compute_properties(G)` runs every property and returns a dict keyed by
name; failures become NaN so a single exception never kills the batch.
"""

from __future__ import annotations

import statistics
from typing import Any, Callable, Dict, List, Optional

import networkx as nx


Apsp = Dict[Any, Dict[Any, int]]


# ---------- shared helpers ----------

def _undirected(G: nx.Graph) -> nx.Graph:
    """Return an undirected view of `G`, or `G` itself when already undirected."""
    return G.to_undirected(as_view=True) if G.is_directed() else G


def _simple_undirected(G: nx.Graph) -> nx.Graph:
    """Undirected, non-multi view for routines (triangles, clustering) that
    don't accept MultiGraph inputs."""
    UG = _undirected(G)
    return nx.Graph(UG) if UG.is_multigraph() else UG


def _connected_components(G: nx.Graph) -> List[nx.Graph]:
    """List of connected-component subgraphs (undirected sense)."""
    UG = _undirected(G)
    return [UG.subgraph(c).copy() for c in nx.connected_components(UG)]


def _component_weighted_sum(G: nx.Graph, fn: Callable[[nx.Graph], float]) -> float:
    """Weighted sum of `fn(component)` by component node count.

    Mirrors the disconnected-graph handling of `kruskal_stress` /
    `neighbourhood_preservation` (paper §3.3), but uses node count as the
    weight since these properties are topological, not layout-dependent.
    Singleton components contribute zero weight; returns NaN when every
    component has fewer than two nodes.
    """
    scores: List[float] = []
    weights: List[int] = []
    for sub in _connected_components(G):
        n = sub.number_of_nodes()
        if n < 2:
            continue
        scores.append(float(fn(sub)))
        weights.append(n)
    total = sum(weights)
    if total == 0:
        return float("nan")
    return sum(s * w for s, w in zip(scores, weights)) / total


def _degrees(G: nx.Graph) -> List[int]:
    return [d for _, d in G.degree()]


# ---------- basic counts & flags ----------

def n_nodes(G: nx.Graph) -> int:
    """Number of nodes."""
    return G.number_of_nodes()


def n_edges(G: nx.Graph) -> int:
    """Number of edges (counts parallel edges in a multigraph)."""
    return G.number_of_edges()


def density(G: nx.Graph) -> float:
    """Edge density in [0, 1]."""
    return nx.density(G)


def is_directed(G: nx.Graph) -> bool:
    return G.is_directed()


def is_multigraph(G: nx.Graph) -> bool:
    return G.is_multigraph()


def n_self_loops(G: nx.Graph) -> int:
    return nx.number_of_selfloops(G)


def n_connected_components(G: nx.Graph) -> int:
    """Connected component count (weakly connected if directed)."""
    if G.is_directed():
        return nx.number_weakly_connected_components(G)
    return nx.number_connected_components(G)


def is_connected(G: nx.Graph) -> bool:
    """Whether the graph is connected (weakly connected if directed)."""
    if G.number_of_nodes() == 0:
        return False
    if G.is_directed():
        return nx.is_weakly_connected(G)
    return nx.is_connected(G)


# ---------- degree statistics ----------

def min_degree(G: nx.Graph) -> int:
    ds = _degrees(G)
    return min(ds) if ds else 0


def max_degree(G: nx.Graph) -> int:
    ds = _degrees(G)
    return max(ds) if ds else 0


def mean_degree(G: nx.Graph) -> float:
    ds = _degrees(G)
    return sum(ds) / len(ds) if ds else 0.0


def degree_std(G: nx.Graph) -> float:
    """Population standard deviation of the degree sequence."""
    ds = _degrees(G)
    if len(ds) < 2:
        return 0.0
    return statistics.pstdev(ds)


# ---------- structural classes ----------

def is_tree(G: nx.Graph) -> bool:
    try:
        return nx.is_tree(G)
    except nx.NetworkXPointlessConcept:
        return False


def is_forest(G: nx.Graph) -> bool:
    try:
        return nx.is_forest(G)
    except nx.NetworkXPointlessConcept:
        return False


def is_bipartite(G: nx.Graph) -> bool:
    return nx.is_bipartite(G)


def is_planar(G: nx.Graph) -> bool:
    """Whether the graph has a planar embedding (Kuratowski's theorem)."""
    planar, _ = nx.check_planarity(G)
    return planar


def is_dag(G: nx.Graph) -> bool:
    """Directed acyclic graph test. False on undirected inputs."""
    return G.is_directed() and nx.is_directed_acyclic_graph(G)


def is_regular(G: nx.Graph) -> bool:
    """Every node has the same degree (empty graph returns True vacuously)."""
    ds = _degrees(G)
    if not ds:
        return True
    return min(ds) == max(ds)


def is_eulerian(G: nx.Graph) -> bool:
    try:
        return nx.is_eulerian(G)
    except nx.NetworkXError:
        return False


# ---------- distances (per-component aggregation) ----------

def compute_apsp(G: nx.Graph) -> Apsp:
    """Compute all-pairs-shortest-path-length on `G`'s undirected view.

    Shared between the three distance properties (diameter, radius,
    avg_shortest_path_length) and `kruskal_stress`. Precompute once and
    pass the result into each function's `apsp` kwarg to avoid redundant
    BFS passes.
    """
    UG = _undirected(G)
    return dict(nx.all_pairs_shortest_path_length(UG))


def _diameter_from_apsp(nodes: List[Any], apsp: Apsp) -> int:
    """Max pairwise distance within a single component."""
    return max(
        apsp[u][v]
        for u in nodes
        for v in nodes
        if u != v
    )


def _radius_from_apsp(nodes: List[Any], apsp: Apsp) -> int:
    """Min eccentricity within a single component."""
    return min(
        max(apsp[u][v] for v in nodes if v != u)
        for u in nodes
    )


def _avg_spl_from_apsp(nodes: List[Any], apsp: Apsp) -> float:
    n = len(nodes)
    if n < 2:
        return 0.0
    total = sum(apsp[u][v] for u in nodes for v in nodes if u != v)
    return total / (n * (n - 1))


def _distance_property(
    G: nx.Graph,
    nx_fn: Callable[[nx.Graph], float],
    apsp_fn: Callable[[List[Any], Apsp], float],
    apsp: Optional[Apsp],
) -> float:
    """Per-component weighted sum, routing through either networkx or the
    apsp-based helper depending on whether a precomputed dict is supplied."""
    if apsp is not None:
        per_component = lambda sub: apsp_fn(list(sub.nodes()), apsp)
    else:
        per_component = nx_fn
    return _component_weighted_sum(G, per_component)


def diameter(G: nx.Graph, *, apsp: Optional[Apsp] = None) -> float:
    """Weighted sum of per-component diameters by component node count.

    `apsp` — optional precomputed APSP (see `compute_apsp`); avoids a
    re-run of the per-component BFS when multiple distance properties or
    `kruskal_stress` are computed on the same graph.
    """
    return _distance_property(G, nx.diameter, _diameter_from_apsp, apsp)


def radius(G: nx.Graph, *, apsp: Optional[Apsp] = None) -> float:
    """Weighted sum of per-component radii by component node count."""
    return _distance_property(G, nx.radius, _radius_from_apsp, apsp)


def avg_shortest_path_length(G: nx.Graph, *, apsp: Optional[Apsp] = None) -> float:
    """Weighted sum of per-component averages by component node count."""
    return _distance_property(G, nx.average_shortest_path_length, _avg_spl_from_apsp, apsp)


# ---------- clustering / triangles ----------

def n_triangles(G: nx.Graph) -> int:
    """Number of triangles (directed graphs are reduced to their undirected
    twin; multigraphs are reduced to simple graphs)."""
    UG = _simple_undirected(G)
    return sum(nx.triangles(UG).values()) // 3


def average_clustering(G: nx.Graph) -> float:
    """Average of the local clustering coefficient across nodes."""
    UG = _simple_undirected(G)
    return nx.average_clustering(UG)


def transitivity(G: nx.Graph) -> float:
    """Global clustering coefficient: 3 × triangles / triads."""
    UG = _simple_undirected(G)
    return nx.transitivity(UG)


# ---------- assortativity ----------

def degree_assortativity(G: nx.Graph) -> float:
    """Pearson correlation of degrees at the ends of each edge. Returns NaN
    on graphs where the correlation is undefined (e.g. every degree equal)."""
    try:
        return float(nx.degree_assortativity_coefficient(G))
    except (nx.NetworkXError, ValueError, ZeroDivisionError):
        return float("nan")


# ---------- batch entry point ----------

PROPERTY_NAMES: List[str] = [
    # basic
    "n_nodes", "n_edges", "density",
    "is_directed", "is_multigraph", "n_self_loops",
    "n_connected_components", "is_connected",
    # degree
    "min_degree", "max_degree", "mean_degree", "degree_std",
    # structural
    "is_tree", "is_forest", "is_bipartite", "is_planar",
    "is_dag", "is_regular", "is_eulerian",
    # distances
    "diameter", "radius", "avg_shortest_path_length",
    # clustering
    "n_triangles", "average_clustering", "transitivity",
    # assortativity
    "degree_assortativity",
]


_APSP_DEPENDENT = {"diameter", "radius", "avg_shortest_path_length"}


def compute_properties(
    G: nx.Graph,
    *,
    apsp: Optional[Apsp] = None,
) -> Dict[str, Any]:
    """Return every property in `PROPERTY_NAMES` as a dict.

    `apsp` — optional precomputed APSP shared with `kruskal_stress` and
    other distance callers. When None, each distance property computes its
    own APSP per component.

    Any exception during a single property becomes NaN so the rest of the
    batch row survives.
    """
    mod = globals()
    out: Dict[str, Any] = {}
    for name in PROPERTY_NAMES:
        try:
            if name in _APSP_DEPENDENT:
                out[name] = mod[name](G, apsp=apsp)
            else:
                out[name] = mod[name](G)
        except Exception:
            out[name] = float("nan")
    return out
