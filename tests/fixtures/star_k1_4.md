# star_k1_4

Four-pointed axis-aligned star: centre `c=(0,0)` with legs to
`e=(1,0)`, `s=(0,1)`, `w=(-1,0)`, `n=(0,-1)`. Degrees: `c=4`, leaves=1.

| Metric | Expected | Derivation |
|---|---|---|
| AR (min/avg) | 1 | Centre has 4 legs at 90° intervals (perfect). Leaves have degree 1 and are ignored. |
| Asp | 1 | Bbox 2×2. |
| CA | 1 | No crossings. |
| EC | 1 | m=4, `c_all = C(4,2) = 6`, `c_deg = C(4,2) = 6` (from the degree-4 centre), `c_max = 0`. |
| ELD | 1 | All legs unit length. |
| EO | 1 | All four legs axis-aligned. |
| GR (edges) | 1 | Each leg's disk has radius 0.5; other leaves lie at distance 1 from the origin, outside the disk. |
| NR | 0.5 | Min pair distance = 1 (centre-leaf); max = 2 (between opposite leaves, e.g. e and w). |
