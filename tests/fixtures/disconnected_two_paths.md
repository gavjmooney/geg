# disconnected_two_paths

Two collinear path components:

- `P3`: `a=(0,0)`, `b=(1,0)`, `c=(2,0)` with edges `a-b`, `b-c`.
- `P2`: `d=(4,0)`, `e=(5,0)` with edge `d-e`.

Purpose: close the DQ-1 loop — exercises the per-component weighted-sum
aggregation that KSM, NP, and the distance properties all apply to
disconnected graphs.

| Metric | Expected | Reason |
|---|---|---|
| AR (min/avg) | 1 | Only `b` has degree ≥ 2; its two legs are collinear → gap 180° → perfect. Endpoints (degree 1) are excluded. |
| Asp | 1 | Height = 0 (all nodes collinear) → paper §3.2 degenerate branch. |
| CA | 1 | No crossings. |
| EC | 1 | Three edges, no crossings; `c_max > 0`. |
| ELD | 1 | All edges unit length. |
| EO | 1 | All edges horizontal → δ = 0. |
| GR (edges) | 1 | Every edge's diameter disk is empty of non-endpoint vertices. |
| KSM | 1 | Per-component: each path is drawn at graph-theoretic unit spacing → zero stress. Weighted by component node counts `(1·3 + 1·2)/(3 + 2) = 1`. |
| NR | 1/5 | Min pair distance = 1 (any adjacent pair). Max pair distance = `|a − e| = 5` (inter-component). |
| NEO | 1 | No non-endpoint node lies closer than ε ≈ 0.02·diag to any edge. |
