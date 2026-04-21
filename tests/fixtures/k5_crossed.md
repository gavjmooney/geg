# k5_crossed

K5 drawn on a regular pentagon with unit circumradius, apex at `(0, -1)`.
Vertices `v0..v4` placed at `(cos(−90° + 72°·i), sin(−90° + 72°·i))`.
All `C(5, 2) = 10` pairs are edges: the 5 pentagon sides plus the 5
diagonals that form a pentagram.

The pentagram has exactly **5 crossings** at the interior star points
(no side crosses any chord; each pair of diagonals that does not share
an endpoint crosses exactly once, and there are `C(5,2) − 5 = 5` such
pairs).

Let `s = sin(π/5)` and `c = sin(2π/5)` (pentagon side and chord lengths
are `2s` and `2c`). `φ = (1 + √5) / 2` and `c / s = φ`.

| Metric | Expected | Reason |
|---|---|---|
| EC | 2/3 | `m = 10`, `c_all = C(10, 2) = 45`, `c_deg = 5 · C(4, 2) = 30`, `c_max = 15`. Pentagram has 5 crossings → `1 − 5/15 = 2/3`. |
| NR | `s / c = 1/φ ≈ 0.618` | Min pair distance = pentagon side `2s`; max pair distance = pentagon diagonal `2c`. |
| ELD | `(s + c) / (2c)` | `ideal = (5·2s + 5·2c) / 10 = s + c`. For every edge, absolute deviation is `|L − ideal| = c − s` (for chords) or `s − c` (for sides), magnitude `c − s` in both cases. Relative deviation is `(c − s) / (s + c)` per edge. `ELD = 1 / (1 + (c − s)/(s + c)) = (s + c) / (2c)`. |
| NEO | 1 | Each chord is ~0.53 units from the nearest non-endpoint vertex; far above ε ≈ 0.02·diag ≈ 0.057. |

Not pinned (non-trivial closed forms; verify empirically via
`METRIC_DELTAS.md`):

- `AR`, `CA`, `EO`, `KSM`, `NP`, `GR` — involve pentagon-angle
  trigonometry and multi-term geometric reasoning; better captured by
  a regression fixture than a hand derivation.
