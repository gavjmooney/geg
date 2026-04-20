# equilateral_triangle

Nodes `a=(0,0), b=(1,0), c=(0.5, √3/2)` with all three edges present.

Exercises the paper §3.2 interpretation of an equilateral layout: unit
edge lengths, 60° interior angles, 30° and 60° segment angles to the
horizontal axis.

| Metric | Expected | Derivation |
|---|---|---|
| AR (min/avg) | 1/3 | Each vertex has degree 2. Gaps around each vertex = [60°, 300°]. `min = 60`, `ideal = 180`, shortfall `(180-60)/180 = 2/3`. `AR = 1 - 2/3 = 1/3`. The avg variant gives the same answer by symmetry. |
| Asp | √3/2 | Bbox width = 1, height = √3/2; `h/w = √3/2` (since h ≤ w). |
| CA | 1 | No crossings. |
| EC | 1 | m=3, all vertices degree 2. `c_all = 3`, `c_deg = 3`, `c_max = 0` → return 1. |
| ELD | 1 | All edges unit length. |
| EO | 5/9 | Segment angles to horizontal axis: 0° (a-b), 60° (b-c, direction (-0.5, √3/2)), 60° (c-a, direction (-0.5, -√3/2)). Per-edge `δ = min(θ, \|90-θ\|, 180-θ)/45`. → `δ = 0, 2/3, 2/3`. Mean = 4/9. `EO = 1 - 4/9 = 5/9`. |
| GR (edges) | 1 | For each edge, the opposite vertex lies at distance √3/2 from the midpoint, which exceeds the disk radius 1/2. |
| KSM | 1 | All graph distances = all layout distances = 1. |
| NP | 1 | K3: each node's two nearest are the other two. `K = A`. |
| NR | 1 | All pair distances = 1. |
