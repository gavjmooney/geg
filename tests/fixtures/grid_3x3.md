# grid_3x3

3×3 node grid with standard grid edges — 12 edges total (no diagonals).
Planar, all edges axis-aligned. Node positions `(i, j)` for
`i, j ∈ {0, 1, 2}`.

Degree distribution: 4 corners (degree 2), 4 side-midpoints (degree 3), 1 centre (degree 4).

| Metric | Expected | Derivation |
|---|---|---|
| AR (min) | 2/3 | Corners: perpendicular legs, shortfall 0.5. Side-midpoints: gaps `[90, 90, 180]`, min=90, ideal=120 → shortfall 1/4. Centre: all four 90° gaps → 0. Sum over 9 vertices = 4·0.5 + 4·0.25 + 0 = 3. Mean = 1/3. AR = 1 - 1/3 = 2/3. |
| AR (avg) | 17/27 ≈ 0.6296 | Corners: `\|90-180\| = \|270-180\| = 90`, mean=90, norm=0.5. Side-midpoints: deviations `\|30, 30, 60\|`, mean=40, norm=1/3. Centre: 0. Sum = 4·0.5 + 4·(1/3) = 10/3. Mean = 10/27. AR = 1 - 10/27 = 17/27. |
| Asp | 1 | Bbox 2×2. |
| CA | 1 | No crossings. |
| EC | 1 | Planar embedding, no crossings. |
| ELD | 1 | All edges unit length. |
| EO | 1 | All edges horizontal or vertical. |
| GR (edges) | 1 | Each edge's disk has radius 0.5; the only other candidates are at grid distance ≥ 1 → outside. |
| NR | 1/(2√2) | Min = 1 (grid neighbour), max = 2√2 (diagonally-opposite corners). |
| NU | 1 | 3×3 grid partition with one node per cell. |

