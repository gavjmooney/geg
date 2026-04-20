# single_edge

Nodes `a=(0,0)`, `b=(1,0)`. One horizontal edge `a-b`.

Every metric is trivially or vacuously 1 — this fixture is a smoke test.

| Metric | Expected | Reason |
|---|---|---|
| AR (min/avg) | 1 | Both nodes have degree 1; no eligible vertices → vacuous 1. |
| Asp | 1 | Height = 0 → paper §3.2 degenerate branch. |
| CA | 1 | No crossings. |
| EC | 1 | `c_max = C(1,2) - 0 = 0` → return 1. |
| ELD | 1 | Single edge → uniform by construction. |
| EO | 1 | Horizontal edge → δ=0. |
| GR (edges) | 1 | No other vertices to place in the diameter disk. |
| GR (nodes) | 1 | `num_nodes ≤ 2` → return 1. |
| KSM | 1 | 2 nodes, unit edge → `d_ij = x_ij = 1` → zero stress. |
| NP | 1 | k = 1, each node's nearest is the other → `A == K`. |
| NR | 1 | Single pair → min = max. |
| NU | 1 | `width = 1, height = 0` → collapsed to 1D grid with 1 node per cell. |
