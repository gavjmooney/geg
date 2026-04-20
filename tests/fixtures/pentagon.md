# pentagon

Regular pentagon with unit circumradius, apex at `(0, -1)`. Vertices at
`(cos(-90° + k·72°), sin(-90° + k·72°))` for k=0..4. Only the five cycle
edges (sides) are drawn — no diagonals.

| Metric | Expected | Derivation |
|---|---|---|
| AR (min/avg) | 0.6 | Each vertex has degree 2. The interior angle of a regular pentagon is 108°, so gaps around each vertex = [108°, 252°]. min=108, ideal=180, shortfall `(180-108)/180 = 0.4`. AR = 0.6. For the avg variant, `\|108-180\| = \|252-180\| = 72`, mean = 72, normalised = 72/180 = 0.4, AR = 0.6. |
| CA | 1 | No crossings. |
| EC | 1 | All vertices degree 2 → `c_max = 0`. |
| ELD | 1 | All sides of a regular pentagon have equal length. |
| GR (edges) | 1 | Each side's diameter disk lies entirely inside the pentagon's circumscribed disk and doesn't enclose the opposite vertices. |

Skipped: EO (angles depend on rotation; sides of a regular pentagon are not
axis-aligned, so there's a clean but somewhat messy number here); NU, NP,
NR, Asp (well-defined but not hand-computed for this fixture).
