import math
from typing import Dict, Tuple, Hashable
import networkx as nx

def _squared_distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return dx * dx + dy * dy


def gabriel_ratio_edges(G: nx.Graph, tol: float = 1e-12) -> float:
    """
    Compute the Gabriel ratio of a straight-line drawing of G.

    An edge (u, v) is a Gabriel edge if the open disk with diameter uv
    contains no other node of the graph. All edges are assumed to be
    straight lines from node to node (edge paths are ignored).

    Returns the fraction of unique, non-self-loop edges that satisfy the
    Gabriel criterion. If there are no such edges, returns 1.0.
    """
    # Collect node positions
    pos: Dict[Hashable, Tuple[float, float]] = {
        n: (float(data["x"]), float(data["y"])) for n, data in G.nodes(data=True)
        if "x" in data and "y" in data
    }

    # Build a set of unique undirected edges (skip self-loops)
    edge_keys = set()
    for u, v in G.edges():
        if u == v:
            continue
        # Skip edges if positions are missing
        if u not in pos or v not in pos:
            continue
        a, b = (u, v) if u <= v else (v, u)
        edge_keys.add((a, b))

    if not edge_keys:
        return 1.0

    gabriel_count = 0
    nodes = list(pos.keys())

    for u, v in edge_keys:
        pu = pos[u]
        pv = pos[v]
        # Midpoint and radius^2 of the disk having uv as diameter
        mid = ((pu[0] + pv[0]) * 0.5, (pu[1] + pv[1]) * 0.5)
        r2 = _squared_distance(pu, pv) * 0.25

        # Zero-length edge (overlapping nodes): treat as non-Gabriel
        if r2 <= tol:
            continue

        is_gabriel = True
        for w in nodes:
            if w == u or w == v:
                continue
            pw = pos.get(w)
            if pw is None:
                continue
            # Inside the open disc if dist^2 < r^2 - tol
            if _squared_distance(pw, mid) < r2 - tol:
                is_gabriel = False
                break

        if is_gabriel:
            gabriel_count += 1

    return gabriel_count / len(edge_keys)



def gabriel_ratio_nodes(G: nx.Graph, tol: float = 1e-12) -> float:
    """
    For each unique, non-self-loop straight edge (u, v), count nodes w that lie
    strictly inside the open disk with diameter uv. Sum these "non-conforming"
    nodes over all considered edges. Normalize by an adjusted upper bound on
    possible violations: start from m * (n - 2) and, for each violation (edge, w),
    subtract 1 from the bound if w is adjacent to u and subtract 1 if w is
    adjacent to v.

    Returns a value in [0, 1]. If the adjusted upper bound becomes non-positive,
    returns 1.0.
    """
    # Collect node positions
    pos: Dict[Hashable, Tuple[float, float]] = {
        n: (float(data["x"]), float(data["y"])) for n, data in G.nodes(data=True)
        if "x" in data and "y" in data
    }

    # Unique undirected edges with positions (skip self-loops)
    edge_keys = set()
    for u, v in G.edges():
        if u == v:
            continue
        if u not in pos or v not in pos:
            continue
        a, b = (u, v) if u <= v else (v, u)
        edge_keys.add((a, b))

    nodes = list(pos.keys())
    num_nodes = len(nodes)
    num_edges = len(edge_keys)

    # Initial upper bound: m * (n - 2)
    possible_non_conforming = num_edges * max(0, num_nodes - 2)
    num_non_conforming = 0

    if num_edges == 0 or num_nodes <= 2:
        return 1.0

    for u, v in edge_keys:
        pu = pos[u]
        pv = pos[v]
        mid = ((pu[0] + pv[0]) * 0.5, (pu[1] + pv[1]) * 0.5)
        r2 = _squared_distance(pu, pv) * 0.25

        for w in nodes:
            if w == u or w == v:
                continue
            pw = pos[w]
            # Inside the open disc if dist^2 < r^2 - tol
            if r2 > tol and _squared_distance(pw, mid) < r2 - tol:
                num_non_conforming += 1
                # Subtract adjacency cases from the bound
                if G.has_edge(u, w) or G.has_edge(w, u):
                    possible_non_conforming -= 1
                if G.has_edge(v, w) or G.has_edge(w, v):
                    possible_non_conforming -= 1

    if possible_non_conforming <= 0:
        return 1.0

    ratio = 1.0 - (num_non_conforming / possible_non_conforming)
    if ratio < 0.0:
        return 0.0
    if ratio > 1.0:
        return 1.0
    return ratio
