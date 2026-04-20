# long_edge_path

Four collinear nodes at `a=0, b=1, c=2, d=12` along the x-axis; edges form a
path a-b-c-d with lengths 1, 1, 10. One deliberately-long edge stresses ELD.

| Metric | Expected | Derivation |
|---|---|---|
| AR (min/avg) | 1 | Middle vertices have degree 2 with legs at 0° and 180° → gaps [180, 180] → ideal match. |
| Asp | 1 | h = 0 (collinear). |
| CA | 1 | No crossings. |
| EC | 1 | Tree topology, no crossings. |
| EO | 1 | All edges horizontal. |
| **ELD** | **1/2** | `L_ideal = (1+1+10)/3 = 4`. Relative deviations `|1-4|/4 = 3/4` (×2) and `|10-4|/4 = 6/4 = 3/2`. Sum = 3. Mean = 1. `ELD = 1/(1+1) = 1/2`. |
| GR (edges) | 1 | For every edge, the midpoint-to-outside-node distance exceeds the disk radius (verify: edge `c-d` disk has radius 5 and mid (7, 0); `a` is 7 units away, on the boundary, not strictly inside). |
| NR | 1/12 | Min = 1 (`a-b` or `b-c`); max = 12 (`a-d`). |
