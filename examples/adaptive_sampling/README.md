# Adaptive curvature-aware sampling — visual showcase

Paired SVGs demonstrating `geg._paths.flatten_path_adaptive` on five
curve-heavy drawings. For each drawing:

- `{name}_original.svg` — the true SVG path (Q / C arcs), rendered
  natively by the browser.
- `{name}_sampled.svg` — the polyline produced by adaptive flattening
  at `flatness_fraction = 0.005` (0.5% of the node-bbox diagonal),
  drawn as straight-line segments with a red dot at each sample point.
  The sampled polyline is indistinguishable from the true curve at any
  reasonable viewing scale; the sampling density visible in the dots
  is what varies.

Run from the package root to regenerate:

```
python -m examples.adaptive_sampling.generate
```

## The drawings

| Drawing | What it exercises |
|---|---|
| `sine_wave` | Four mild Q arcs alternating above/below a baseline. Samples spread evenly across each arch. |
| `flower` | Six cubic petals radiating from a hub. Each petal's curvature is moderate; dots cluster slightly at the bulge. |
| `pinwheel` | Eight Q-arc spokes bending counterclockwise. Mirror-symmetric curves show the sampler is direction-agnostic. |
| `tangled_s` | Four deliberately tight cubic S-curves crossing through a common region. **Inflection points are where the extra density lands** — the sampler spends its budget where curvature sign flips, not where the curve is monotonic. |
| `flow_network` | Mixed-curvature flow diagram: some gentle connectors between "hidden-layer" nodes get just 2-3 samples, while the dramatic U-turn from output back to input is densely sampled. |
| `signature` | A **single compound path** interleaving 5 straight `L` segments with 4 Beziers of varying curvature (gentle Q, tight C S-curve, mild Q, shallow C). Shows that within one path: Line segments stay as 2 points, and each non-Line segment is flattened adaptively and independently — a tight cubic gets many samples while an adjacent gentle arc gets only a handful. |

## Reading the sampled SVGs

- **Few dots on a segment** — the polyline approximated the true curve
  to within `flatness_tol` after one or two subdivisions. The curve is
  nearly flat at this tolerance.
- **Dense dot clusters** — the recursion subdivided multiple times to
  keep midpoint-to-chord deviation under tolerance. That region has
  high curvature (tight bend, inflection, U-turn).

A uniform fixed-N sampler would place 100 dots per segment regardless
of shape — most wasted on straight-ish regions, potentially not enough
at sharp corners. Adaptive flattening redirects that budget.

## Sample counts at `flatness_fraction = 0.005`

| Drawing | Curves (non-Line segments) | Total sample points |
|---|---|---|
| `sine_wave` | 4 | 20 |
| `flower` | 6 | 42 |
| `pinwheel` | 8 | 40 |
| `tangled_s` | 4 | 60 |
| `flow_network` | 10 | 41 |
| `signature` | 4 (in a single 9-segment path) | 26 |

For comparison, fixed-N at `samples_per_curve = 100` would produce
400 / 600 / 800 / 400 / 1000 / 400 points respectively — one to two
orders of magnitude more samples on graphs where most curves are
mild, and only slightly more on graphs with tight curves. The
`signature` row is particularly telling: a 9-segment path with 5
Lines and 4 Beziers collapses from 400 samples (100 per curve) to
26 (straight pieces stay as 2 points; each curve gets 3-8).
