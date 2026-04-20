# polyline_bend

Single L-shaped polyline edge from `a=(0,0)` to `b=(2,2)` via a 90° bend at
`(2,0)`. The path string is `M0,0 L2,0 L2,2`.

Exercises the bends-promotion pathway of `edge_orthogonality` (per paper
§3.2 eq. (5)–(6)) — the per-edge deviation is a length-weighted average
over the two polyline segments.

| Metric | Expected | Derivation |
|---|---|---|
| Asp | 1 | Promoted bbox = 2×2 (both bend and target extend the bbox). |
| EC | 1 | `c_max = 0` (m=1). |
| ELD | 1 | Single edge. |
| EO | 1 | Segment 1 (horizontal, length 2): `δ=0`. Segment 2 (vertical, length 2): `δ=0`. `δ_e = 0 + 0 = 0`. EO = 1. |

Metrics not fixed analytically here: AR (bend point is not a graph vertex;
both endpoints have degree 1, so AR is vacuous → 1, but that's trivial).
