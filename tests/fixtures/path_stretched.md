# path_stretched

Nodes `a=(0,0), b=(1,0), c=(3,0), d=(6,0)` with edges `a-b`, `b-c`, `c-d`.
Edge lengths are 1, 2, 3.

Non-uniform spacing on purpose: a uniform collinear path ties the k-nearest-
neighbour distances at the middle vertices, which makes `neighbourhood_
preservation` non-deterministic in the tie-break. Stretched spacing avoids this.

| Metric | Expected | Derivation |
|---|---|---|
| AR (min/avg) | 1 | Middle vertices have degree 2 with legs at 0° and 180° → gaps 180/180 → ideal match. |
| Asp | 1 | Height = 0. |
| CA | 1 | No crossings. |
| EC | 1 | m=3, deg = [1,2,2,1], c_all=3, c_deg=(2·1+2·1)/2=2, c_max=1. Zero crossings → 1. |
| EO | 1 | Every edge is horizontal. |
| ELD | 3/4 | `L_ideal = (1+2+3)/3 = 2`. Relative deviations = 1/2, 0, 1/2; average = 1/3. `ELD = 1/(1 + 1/3) = 3/4`. |
| GR (edges) | 1 | Each edge's diameter disk has radius at most 1.5; the other two nodes are always ≥ 1.5 units away from the midpoint. |
| NR | 1/6 | min pair distance = 1 (a-b); max = 6 (a-d). |

Skipped metrics: KSM, NP, NU (not pinned — KSM non-trivial to hand-compute due
to isotonic regression on three pairs; NU depends on grid rounding of the 1D
bbox; NP is well-defined here but not the easiest thing to write out).
