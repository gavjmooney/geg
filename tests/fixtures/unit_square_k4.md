# unit_square_k4

Nodes `a=(0,0), b=(1,0), c=(1,1), d=(0,1)`. All six K4 edges present:
four axis-aligned sides (`a-b`, `b-c`, `c-d`, `d-a`) + two diagonals
(`a-c`, `b-d`). The diagonals cross at `(0.5, 0.5)` at 90°.

| Metric | Expected | Derivation |
|---|---|---|
| Asp | 1 | Bbox is exactly square (1×1). |
| CA | 1 | Exactly one crossing, at the ideal 90°. |
| EC | 2/3 | m=6, all vertices degree 3. `c_all = C(6,2) = 15`, `c_deg = 4·C(3,2) = 12`, `c_max = 3`. One crossing → `EC = 1 - 1/3 = 2/3`. |
| ELD | (see below) | Four sides of length 1, two diagonals of length √2; `L_ideal = (4 + 2√2)/6 = (2 + √2)/3`. |
| EO | 2/3 | Four axis-aligned edges (`δ=0`) + two 45° diagonals (`δ=1`). Mean `δ = 2/6 = 1/3`. |
| NR | 1/√2 | Min pair = 1 (side), max pair = √2 (diagonal). |
| NU | 1 | 4 nodes, 2×2 grid → exactly one node per cell. |

**ELD derivation in full.** Let `L_ideal = (2 + √2)/3`. Per-edge relative
deviation: sides contribute `|1 - L_ideal| / L_ideal`; diagonals contribute
`|√2 - L_ideal| / L_ideal`. Average over 6 edges; then `ELD = 1 / (1 + avg)`.
The exact value (≈ 0.852) is computed from the symbolic form in
`_builder.py` and asserted against the implementation.
