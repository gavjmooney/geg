# unit_square_cycle

The 4-cycle `a-b-c-d-a` on the unit square — sides only, no diagonals.
Planar, all edges axis-aligned.

| Metric | Expected | Derivation |
|---|---|---|
| AR (min/avg) | 0.5 | Each vertex has degree 2 with perpendicular legs. Gaps `[90°, 270°]`, `min = 90`, `ideal = 180`, shortfall `(180-90)/180 = 0.5`. Symmetric, so avg gives the same number. |
| Asp | 1 | Bbox 1×1. |
| CA | 1 | No crossings. |
| EC | 1 | m=4, all degree 2. `c_all = 6`, `c_deg = 4·1 = 4`, `c_max = 2`, crossings = 0. |
| ELD | 1 | All edges unit length. |
| EO | 1 | All four edges axis-aligned. |
| GR (edges) | 1 | Each side's disk has radius 0.5; the two non-endpoint vertices are at distance √2·0.5 ≈ 0.707 (i.e. the opposite corner is 1 unit away, the adjacent corner is √2/2 away from mid). Wait — check: edge `a-b` has midpoint (0.5, 0), radius 0.5. Opposite corners `c=(1,1)` and `d=(0,1)` are at distance √1.25 ≈ 1.118, outside. Gabriel. |
| NR | 1/√2 | Min pair = 1 (adjacent corners), max = √2 (opposite corners). |
| NU | 1 | 2×2 grid with 1 node per cell. |
