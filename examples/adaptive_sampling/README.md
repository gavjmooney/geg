# Adaptive curvature-aware sampling — visual showcase

Paired SVGs demonstrating `geg._paths.flatten_path_adaptive` on nine
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
| `dual_arc` | Two edges on the same drawing — one with a big sweeping Q curve (chord 1000, sagitta 250), one with a tiny Q curve (chord 20, sagitta 5). **Simplest demonstration of multi-scale behaviour.** Big arc → 9 samples; tiny arc → 2 (collapses to a straight line). The tiny arc is visually insignificant at the drawing's absolute tolerance (0.005 × bbox_diag ≈ 5 units ≈ its sagitta), so the sampler correctly treats it as straight. |
| `concentric_arcs` | Four self-similar Q arcs (all sagitta = 0.3 × chord) with chord lengths in a geometric progression 32 → 100 → 320 → 1000. Because tolerance is absolute (graph units), smaller arcs are held to a looser *relative* accuracy than larger ones → sample counts **3 / 5 / 7 / 9** across the sequence. The sampler's budget tracks visual significance in the drawing, not chord-relative curvature. |
| `metropolitan` | Three "cities" far apart connected by long curved "highways", plus a tight local cluster of 4 nodes (short curved "streets") near one city. Highways → 9 samples each; streets → 3; the tightest street-to-centre connector → 2. Shows the sampler distributing its budget across feature sizes spanning more than an order of magnitude within a single realistic graph. |

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
| `dual_arc` | 2 | 11 |
| `concentric_arcs` | 4 | 24 |
| `metropolitan` | 8 | 41 |

For comparison, fixed-N at `samples_per_curve = 100` would produce
400 / 600 / 800 / 400 / 1000 / 400 points respectively — one to two
orders of magnitude more samples on graphs where most curves are
mild, and only slightly more on graphs with tight curves. The
`signature` row is particularly telling: a 9-segment path with 5
Lines and 4 Beziers collapses from 400 samples (100 per curve) to
26 (straight pieces stay as 2 points; each curve gets 3-8).

## Manual scale-invariance check

`scale_sweep/` contains the same `signature` drawing rendered at four
different coordinate scales spanning **nine orders of magnitude**:

| File prefix | Coordinate range | `flatness_tol` |
|---|---|---|
| `signature_scale_1e-3` | `[0, 0.3]` | 0.0015 |
| `signature_scale_1`    | `[0, 300]` | 1.5 |
| `signature_scale_1e3`  | `[0, 300 000]` | 1 500 |
| `signature_scale_1e6`  | `[0, 300 000 000]` | 1 500 000 |

Both the SVG layout (600 × 300 canvas) and the `flatness_fraction = 0.005`
parameter are scale-proportional, so the four sampled SVGs should look
**pixel-identical** — same 24 red sample dots, same polyline topology,
same EO / EC / NEO readout in the header. Opening them side by side is
the visual proof of scale invariance.

Programmatic check:

```
max polyline drift (after normalising by k) across scales: 2.8e-14
```

Float-epsilon-level agreement. Any perceptible difference between the
four SVGs is a regression.

## Manual render-size check

`canvas_sweep/` contains the same `signature` drawing (native coord scale)
rendered at five **pixel canvas widths** — 300, 600, 1200, 2400, 3000 px.
The adaptive sampler runs once at `flatness_fraction = 0.005`; the same
26-point polyline is emitted at every size. Only the SVG `width` /
`height` / `viewBox` attributes change.

| File | Canvas dimensions |
|---|---|
| `signature_canvas_300_*` | 300 × 150 px |
| `signature_canvas_600_*` | 600 × 300 px |
| `signature_canvas_1200_*` | 1200 × 600 px |
| `signature_canvas_2400_*` | 2400 × 1200 px |
| `signature_canvas_3000_*` | 3000 × 1500 px |

Use this to eyeball whether the adaptive polyline still looks smooth
at high magnification. Because `flatness_fraction` is defined relative
to graph coordinates, the polyline density is invariant to how large
the browser renders it — if a curve looks jagged at 3000 px but smooth
at 300 px, that means the flatness tolerance is too loose for your
use case. Tighten `flatness_fraction` (0.001 or 0.0005) and regenerate.
