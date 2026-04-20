# diagonal_45

Single edge from `(0,0)` to `(1,1)` — exactly 45° to the horizontal. The EO
worst case.

| Metric | Expected | Derivation |
|---|---|---|
| Asp | 1 | Bbox is 1×1. |
| EC | 1 | `c_max = 0` (m=1). |
| ELD | 1 | Single edge. |
| EO | 0 | θ = 45°. `min(45, \|90-45\|, 180-45)/45 = 45/45 = 1`. Mean `δ = 1`. `EO = 0`. |

This fixture pins the EO-per-edge δ=1 boundary. Together with `diagonal_45`
contributing to a mixed-edge fixture (not yet built), it ensures the scaling
factor 45° in the denominator is correct.
