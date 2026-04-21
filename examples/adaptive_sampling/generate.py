"""Side-by-side visual showcase of curvature-aware flattening.

For each of five curve-heavy drawings this script writes two SVGs:

- ``{name}_original.svg`` — browser renders the true SVG path (Q / C arcs).
- ``{name}_sampled.svg``  — the polyline produced by
  ``_paths.flatten_path_adaptive`` at ``flatness_fraction * diag``
  tolerance, drawn as straight-line segments with a red dot at each
  sample point so the sampling density is visible.

Run from the package root:

    python -m examples.adaptive_sampling.generate
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Callable, Dict

import networkx as nx

from geg._paths import edge_polyline, flatten_path_adaptive


OUT_DIR = Path(__file__).parent
FLATNESS_FRACTION = 0.005  # 0.5% of node-bbox diagonal


# ---------- drawings ----------

def _add_node(G: nx.Graph, name: str, x: float, y: float) -> None:
    G.add_node(name, x=float(x), y=float(y))


def _add_edge(G: nx.Graph, u: str, v: str, path: str) -> None:
    G.add_edge(u, v, polyline=True, path=path)


def build_sine_wave() -> nx.Graph:
    """Five collinear nodes connected by alternating quadratic arcs."""
    G = nx.Graph()
    for i in range(5):
        _add_node(G, f"n{i}", 100.0 * i, 0.0)
    # Control point y alternates sign so arcs alternate above/below the axis.
    for i in range(4):
        sign = -60.0 if i % 2 == 0 else 60.0
        x0, x1 = 100.0 * i, 100.0 * (i + 1)
        cx = 0.5 * (x0 + x1)
        _add_edge(G, f"n{i}", f"n{i+1}", f"M{x0},0 Q{cx},{sign} {x1},0")
    return G


def build_flower() -> nx.Graph:
    """Central hub with six cubic-Bezier petals radiating outward."""
    G = nx.Graph()
    _add_node(G, "c", 0.0, 0.0)
    radius = 100.0
    for i in range(6):
        theta = math.radians(60.0 * i)
        px = radius * math.cos(theta)
        py = radius * math.sin(theta)
        _add_node(G, f"p{i}", px, py)
        # Cubic with control points fanned out to 2/3 radius at ±30° off-axis;
        # that makes the path bulge into a petal shape rather than arcing in
        # one direction.
        r_ctrl = radius * 0.6
        theta_plus = theta + math.radians(35.0)
        theta_minus = theta - math.radians(35.0)
        c1 = (r_ctrl * math.cos(theta_plus), r_ctrl * math.sin(theta_plus))
        c2 = (px - r_ctrl * math.cos(theta_minus) * 0.2,
              py - r_ctrl * math.sin(theta_minus) * 0.2)
        path = f"M0,0 C{c1[0]},{c1[1]} {c2[0]},{c2[1]} {px},{py}"
        _add_edge(G, "c", f"p{i}", path)
    return G


def build_pinwheel() -> nx.Graph:
    """Eight spokes, each bending counterclockwise — a pinwheel swirl."""
    G = nx.Graph()
    _add_node(G, "hub", 0.0, 0.0)
    radius = 120.0
    for i in range(8):
        theta = math.radians(45.0 * i)
        ox = radius * math.cos(theta)
        oy = radius * math.sin(theta)
        _add_node(G, f"s{i}", ox, oy)
        # Control point sits 60° rotated around the midpoint, making a curved
        # spoke instead of a straight ray.
        mid = (0.5 * ox, 0.5 * oy)
        tan_theta = theta + math.radians(90.0)
        offset = radius * 0.35
        cx = mid[0] + offset * math.cos(tan_theta)
        cy = mid[1] + offset * math.sin(tan_theta)
        path = f"M0,0 Q{cx},{cy} {ox},{oy}"
        _add_edge(G, "hub", f"s{i}", path)
    return G


def build_tangled_s() -> nx.Graph:
    """Four S-shaped cubic curves crossing through a common region. Control
    points swing hard so the S-bends are pronounced."""
    G = nx.Graph()
    # Each entry: (node_u, node_v, start, end, swing_amplitude).
    # Swing amplitude controls how far the control points push off the
    # straight chord — larger swing = tighter S shape = denser adaptive
    # sampling.
    SWING = 180.0
    endpoints = [
        ("a0", "a1", (-150, -80), (150,  80)),
        ("b0", "b1", (-150,  80), (150, -80)),
        ("c0", "c1", (-150,   0), (150,   0)),
        ("d0", "d1", (   0, -120), (  0, 120)),
    ]
    for u, v, (ux, uy), (vx, vy) in endpoints:
        _add_node(G, u, ux, uy)
        _add_node(G, v, vx, vy)
        # Unit vector along the chord, and perpendicular to it.
        dx, dy = vx - ux, vy - uy
        L = math.hypot(dx, dy) or 1.0
        tx, ty = dx / L, dy / L
        nx_, ny_ = -ty, tx
        # Cubic S: first control 1/3 along, offset +normal; second control
        # 2/3 along, offset -normal. This creates a symmetric S with
        # amplitude SWING perpendicular to the chord.
        c1x = ux + (L / 3.0) * tx + SWING * nx_
        c1y = uy + (L / 3.0) * ty + SWING * ny_
        c2x = ux + (2.0 * L / 3.0) * tx - SWING * nx_
        c2y = uy + (2.0 * L / 3.0) * ty - SWING * ny_
        path = f"M{ux},{uy} C{c1x:.2f},{c1y:.2f} {c2x:.2f},{c2y:.2f} {vx},{vy}"
        _add_edge(G, u, v, path)
    return G


def build_flow_network() -> nx.Graph:
    """Layered flow diagram: 2 input → 3 hidden → 1 output, fully connected,
    with mixed curvature — near-straight skip paths, sharply hooked ones,
    and one very tight U-turn."""
    G = nx.Graph()
    _add_node(G, "in0", 0.0,   0.0)
    _add_node(G, "in1", 0.0, 120.0)
    _add_node(G, "h0", 200.0,   0.0)
    _add_node(G, "h1", 200.0,  60.0)
    _add_node(G, "h2", 200.0, 120.0)
    _add_node(G, "out", 400.0,  60.0)

    # Input → hidden: mild S-curves
    _add_edge(G, "in0", "h0",
              "M0,0 C80,0 120,0 200,0")
    _add_edge(G, "in0", "h1",
              "M0,0 C70,10 140,50 200,60")
    _add_edge(G, "in0", "h2",
              "M0,0 C60,40 120,100 200,120")
    _add_edge(G, "in1", "h0",
              "M0,120 C60,80 120,20 200,0")
    _add_edge(G, "in1", "h1",
              "M0,120 C70,90 140,70 200,60")
    _add_edge(G, "in1", "h2",
              "M0,120 C80,120 120,120 200,120")

    # Hidden → output: gentle converging curves
    _add_edge(G, "h0",  "out",
              "M200,0 C260,20 340,40 400,60")
    _add_edge(G, "h1",  "out",
              "M200,60 Q300,60 400,60")
    _add_edge(G, "h2",  "out",
              "M200,120 C260,100 340,80 400,60")

    # One tight U-turn as a stress test: out loops back to in1 via a
    # dramatic overshoot below the layout.
    _add_edge(G, "out", "in1",
              "M400,60 C400,250 0,250 0,120")
    return G


def build_signature() -> nx.Graph:
    """A single edge whose path interleaves 5 straight Lines with 4 Bezier
    segments of varying curvature. Demonstrates that within one compound
    path, Line segments collapse to their two endpoints (no sampling
    wasted) while each curved segment is flattened adaptively and
    independently of its neighbours — so a tight cubic next to a gentle
    quadratic gets correspondingly different sample densities."""
    G = nx.Graph()
    _add_node(G, "A",   0.0, 0.0)
    _add_node(G, "B", 300.0, 0.0)
    # M  L     Q        L   C             L     Q       L   C            L
    # 0  30    60       90  140           170   200     230 270          300
    path = (
        "M0,0 L30,0 "                    # straight baseline
        "Q45,-45 60,0 "                  # shallow arch up
        "L90,0 "                         # straight
        "C100,-55 130,55 140,0 "         # tight S-curve
        "L170,0 "                        # straight
        "Q185,20 200,0 "                 # mild arch down
        "L230,0 "                        # straight
        "C240,-18 260,18 270,0 "         # shallow S
        "L300,0"                         # straight to target
    )
    _add_edge(G, "A", "B", path)
    return G


def build_dual_arc() -> nx.Graph:
    """Two edges on the same drawing — one with a big sweeping arc, one
    with a tiny arc near the midpoint. Simplest demonstration of
    adaptive sampling's response to multi-scale features in a single
    graph. flatness_tol = 0.005 × node-bbox-diag ≈ 5 graph units.
    """
    G = nx.Graph()
    _add_node(G, "a",    0.0, 200.0)
    _add_node(G, "b", 1000.0, 200.0)
    _add_node(G, "c",  490.0, 270.0)
    _add_node(G, "d",  510.0, 270.0)
    # Big arc: chord length 1000, peaks ~250 units off the chord.
    _add_edge(G, "a", "b", "M0,200 Q500,-300 1000,200")
    # Tiny arc: chord length 20, peaks ~5 units off the chord.
    _add_edge(G, "c", "d", "M490,270 Q500,260 510,270")
    return G


def build_concentric_arcs() -> nx.Graph:
    """Four Q arcs sharing the same self-similar shape (sagitta = 30 % of
    chord) but with chord lengths in a geometric progression spanning
    ~30× (32 → 1000). Adaptive flattening should produce a similar
    sample count per arc — curvature relative to chord is identical, so
    the per-sub-interval flatness test terminates at the same depth —
    while fixed-N=100 would waste the same 100 samples on every arc
    regardless of its visual size.
    """
    G = nx.Graph()
    chords = [32.0, 100.0, 320.0, 1000.0]
    for i, L in enumerate(chords):
        y = 120.0 * i
        x0 = (1000.0 - L) / 2.0
        x1 = x0 + L
        _add_node(G, f"L{i}", x0, y)
        _add_node(G, f"R{i}", x1, y)
        cx, cy = (x0 + x1) / 2.0, y - 0.6 * L  # peak at sagitta = 0.3 · L
        _add_edge(G, f"L{i}", f"R{i}", f"M{x0},{y} Q{cx},{cy} {x1},{y}")
    return G


def build_metropolitan() -> nx.Graph:
    """Mixed-scale realistic graph: three 'cities' far apart connected by
    long curved 'highways', plus a tight local cluster near one of them
    (short curved 'streets'). The sampler distributes its budget sensibly
    across features that differ in size by more than an order of magnitude
    within the same drawing.
    """
    G = nx.Graph()
    _add_node(G, "C1", 100.0, 500.0)
    _add_node(G, "C2", 900.0, 500.0)
    _add_node(G, "C3", 500.0,  60.0)
    _add_node(G, "L1", 870.0, 470.0)
    _add_node(G, "L2", 930.0, 470.0)
    _add_node(G, "L3", 930.0, 530.0)
    _add_node(G, "L4", 870.0, 530.0)
    # Highways (long cubic curves between cities).
    _add_edge(G, "C1", "C2", "M100,500 C300,200 700,200 900,500")
    _add_edge(G, "C1", "C3", "M100,500 C100,300 350,80 500,60")
    _add_edge(G, "C2", "C3", "M900,500 C900,300 650,80 500,60")
    # Streets (tight local Q curves inside the cluster).
    _add_edge(G, "L1", "L2", "M870,470 Q900,460 930,470")
    _add_edge(G, "L2", "L3", "M930,470 Q940,500 930,530")
    _add_edge(G, "L3", "L4", "M930,530 Q900,540 870,530")
    _add_edge(G, "L4", "L1", "M870,530 Q860,500 870,470")
    # One link from city centre into the cluster.
    _add_edge(G, "C2", "L1", "M900,500 Q880,480 870,470")
    return G


DRAWINGS: Dict[str, Callable[[], nx.Graph]] = {
    "sine_wave":        build_sine_wave,
    "flower":           build_flower,
    "pinwheel":         build_pinwheel,
    "tangled_s":        build_tangled_s,
    "flow_network":     build_flow_network,
    "signature":        build_signature,
    "dual_arc":         build_dual_arc,
    "concentric_arcs":  build_concentric_arcs,
    "metropolitan":     build_metropolitan,
}


# ---------- rendering ----------

SVG_HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
    'width="{w}" height="{h}" viewBox="{vbx} {vby} {vbw} {vbh}">\n'
)


def _layout(G: nx.Graph) -> Dict[str, float]:
    """Pick a canvas that comfortably contains node positions plus a margin
    generous enough to fit typical curve excursions (we don't promote here;
    curves frequently reach outside the node hull, so we pad generously).

    Padding is proportional to the drawing's own extent so the layout stays
    scale-invariant: a graph in [0, 0.001] lays out the same way as one in
    [0, 1e6]. The only floor is for fully-degenerate (zero-extent) cases,
    which only happen when every node shares a position."""
    xs = [d["x"] for _, d in G.nodes(data=True)]
    ys = [d["y"] for _, d in G.nodes(data=True)]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    extent = max(max_x - min_x, max_y - min_y)
    pad = 0.5 * (extent if extent > 0 else 1.0)
    return {
        "min_x": min_x - pad,
        "min_y": min_y - pad,
        "width": (max_x - min_x) + 2 * pad,
        "height": (max_y - min_y) + 2 * pad,
    }


def _flatness_tol(G: nx.Graph) -> float:
    xs = [d["x"] for _, d in G.nodes(data=True)]
    ys = [d["y"] for _, d in G.nodes(data=True)]
    diag = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
    return FLATNESS_FRACTION * diag if diag > 0 else 1.0


def _node_radius(box: Dict[str, float]) -> float:
    return 0.012 * max(box["width"], box["height"])


def _svg_open(box: Dict[str, float], px_width: float = 600.0) -> str:
    w = px_width
    h = px_width * (box["height"] / box["width"])
    return SVG_HEADER.format(
        w=w, h=h,
        vbx=box["min_x"], vby=box["min_y"],
        vbw=box["width"], vbh=box["height"],
    )


def _render_nodes(G: nx.Graph, r: float) -> str:
    parts = []
    for n, attrs in G.nodes(data=True):
        parts.append(
            f'  <circle cx="{attrs["x"]:.3f}" cy="{attrs["y"]:.3f}" '
            f'r="{r:.3f}" fill="#ffffff" stroke="#000000" '
            f'stroke-width="{r * 0.25:.3f}"/>\n'
        )
    return "".join(parts)


def render_original(G: nx.Graph, path: Path) -> None:
    box = _layout(G)
    r = _node_radius(box)
    stroke_w = r * 0.4
    lines = [_svg_open(box)]
    # Title banner
    diag = math.hypot(box["width"], box["height"])
    lines.append(
        f'  <text x="{box["min_x"] + 10}" y="{box["min_y"] + 20}" '
        f'font-family="monospace" font-size="{diag * 0.02:.2f}" '
        f'fill="#999999">ORIGINAL</text>\n'
    )
    for _, _, attrs in G.edges(data=True):
        d = attrs["path"]
        lines.append(
            f'  <path d="{d}" fill="none" stroke="#1f77b4" '
            f'stroke-width="{stroke_w:.3f}"/>\n'
        )
    lines.append(_render_nodes(G, r))
    lines.append("</svg>\n")
    path.write_text("".join(lines), encoding="utf-8")


def render_sampled(G: nx.Graph, path: Path, flatness_tol: float) -> None:
    box = _layout(G)
    r = _node_radius(box)
    stroke_w = r * 0.4
    dot_r = r * 0.35
    lines = [_svg_open(box)]
    diag = math.hypot(box["width"], box["height"])
    # Count samples globally for the header line.
    total_samples = 0
    rendered_edges = []
    for u, v, attrs in G.edges(data=True):
        # Use edge_polyline so endpoint snapping is orientation-aware — an
        # undirected graph's iteration order can yield (u, v) opposite to
        # the path's authored direction; edge_polyline reverses when the
        # path starts closer to target than to source.
        poly = edge_polyline(
            source=(G.nodes[u]["x"], G.nodes[u]["y"]),
            target=(G.nodes[v]["x"], G.nodes[v]["y"]),
            path_str=attrs["path"],
            flatness_tol=flatness_tol,
        )
        total_samples += len(poly)
        rendered_edges.append((u, v, poly))
    lines.append(
        f'  <text x="{box["min_x"] + 10}" y="{box["min_y"] + 20}" '
        f'font-family="monospace" font-size="{diag * 0.02:.2f}" '
        f'fill="#999999">SAMPLED — flatness_fraction={FLATNESS_FRACTION}, '
        f'{total_samples} pts across {len(rendered_edges)} edges</text>\n'
    )
    for u, v, poly in rendered_edges:
        d = "M" + " L".join(f"{x:.3f},{y:.3f}" for x, y in poly)
        lines.append(
            f'  <path d="{d}" fill="none" stroke="#555555" '
            f'stroke-width="{stroke_w:.3f}"/>\n'
        )
    # Sample dots on top of the polyline so they're visible at joins.
    for _, _, poly in rendered_edges:
        # Drop first & last (they coincide with node circles).
        for x, y in poly[1:-1]:
            lines.append(
                f'  <circle cx="{x:.3f}" cy="{y:.3f}" r="{dot_r:.3f}" '
                f'fill="#e74c3c" stroke="none"/>\n'
            )
    lines.append(_render_nodes(G, r))
    lines.append("</svg>\n")
    path.write_text("".join(lines), encoding="utf-8")


def _scale_signature(k: float) -> nx.Graph:
    """Signature drawing with every coordinate multiplied by `k`. The
    flatness_fraction mechanism should produce bit-identical polylines
    (modulo the scale factor) — this is the visual proof of scale
    invariance."""
    import re
    G = build_signature()
    # Scale node positions.
    for _, attrs in G.nodes(data=True):
        attrs["x"] *= k
        attrs["y"] *= k
    # Scale every numeric literal in the path string.
    def scale_literal(m: re.Match) -> str:
        v = float(m.group()) * k
        return f"{v:g}"
    for _, _, attrs in G.edges(data=True):
        attrs["path"] = re.sub(r"-?\d+(?:\.\d+)?", scale_literal, attrs["path"])
    return G


_RENDER_CANVAS = 600.0  # pixel width the sampled SVGs always render at


def _display_transform_to(G: nx.Graph, canvas_width: float):
    """Like `_display_transform` but targets an arbitrary pixel canvas
    width. Used by the canvas_sweep to render the same drawing at a
    range of physical pixel sizes."""
    box = _layout(G)
    extent = max(box["width"], box["height"])
    if extent <= 0:
        return 1.0, 0.0, 0.0, canvas_width, canvas_width
    s = canvas_width / extent
    ox = -box["min_x"] * s
    oy = -box["min_y"] * s
    disp_w = box["width"] * s
    disp_h = box["height"] * s
    return s, ox, oy, disp_w, disp_h


def _display_transform(G: nx.Graph):
    """Return (scale, offset_x, offset_y) mapping graph coords to a
    fixed pixel range `[0, _RENDER_CANVAS]` × `[0, h]`.

    Purpose: decouple the SVG output's coordinate range from the graph's
    native scale. The adaptive flattener still runs on native-scale
    coordinates (that's the point of the sweep — proving computational
    scale invariance), but every emitted SVG uses pixel coords in the
    hundreds-range regardless. Browsers' single-precision internal
    transforms only stay numerically clean up to ~1.7e7; at the native
    1e6 scale, a viewBox spanning 6e8 pushes past that threshold and
    browser rendering visibly degrades. A display-only rescale keeps
    things robust without affecting the computation we're verifying.
    """
    box = _layout(G)
    extent = max(box["width"], box["height"])
    if extent <= 0:
        return 1.0, 0.0, 0.0
    scale = _RENDER_CANVAS / extent
    # Translate so that the viewBox starts at (0, 0).
    return scale, -box["min_x"] * scale, -box["min_y"] * scale


def _render_sampled_with_metrics(
    G: nx.Graph, path: Path, flatness_tol: float, scale_label: str,
) -> None:
    """Variant of render_sampled that (a) overlays the scale label +
    metric readout in the header, and (b) emits every SVG at a fixed
    pixel canvas so the output is robust to browser float-precision
    issues at extreme underlying coordinate scales."""
    from geg import edge_crossings, edge_orthogonality, node_edge_occlusion

    box = _layout(G)
    s, ox, oy = _display_transform(G)

    def tx(x, y):
        return x * s + ox, y * s + oy

    # Use a fixed display canvas; compute render-space node size from
    # the canvas, not the graph coords.
    disp_w = box["width"] * s
    disp_h = box["height"] * s
    r = 0.012 * max(disp_w, disp_h)
    stroke_w = r * 0.4
    dot_r = r * 0.35

    svg_open = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
        f'width="{disp_w:.3f}" height="{disp_h:.3f}" '
        f'viewBox="0 0 {disp_w:.3f} {disp_h:.3f}">\n'
    )
    lines = [svg_open]

    total_samples = 0
    rendered_edges = []
    for u, v, attrs in G.edges(data=True):
        # Polyline is computed at native graph scale (proves invariance).
        poly = edge_polyline(
            source=(G.nodes[u]["x"], G.nodes[u]["y"]),
            target=(G.nodes[v]["x"], G.nodes[v]["y"]),
            path_str=attrs["path"],
            flatness_tol=flatness_tol,
        )
        total_samples += len(poly)
        # Transform to pixel space for emission only.
        rendered_edges.append((u, v, [tx(x, y) for x, y in poly]))

    eo = edge_orthogonality(G, flatness_fraction=FLATNESS_FRACTION)
    ec = edge_crossings(G, flatness_fraction=FLATNESS_FRACTION)
    neo = node_edge_occlusion(G, flatness_fraction=FLATNESS_FRACTION)

    fs = disp_h * 0.045
    lines.append(
        f'  <text x="10" y="{fs * 1.3:.2f}" font-family="monospace" '
        f'font-size="{fs:.2f}" fill="#555555">'
        f'scale={scale_label}  {total_samples} pts</text>\n'
    )
    lines.append(
        f'  <text x="10" y="{fs * 2.5:.2f}" font-family="monospace" '
        f'font-size="{fs * 0.65:.2f}" fill="#999999">'
        f'EO={eo:.6f}  EC={ec:.6f}  NEO={neo:.6f}</text>\n'
    )

    for _, _, poly in rendered_edges:
        d = "M" + " L".join(f"{x:.3f},{y:.3f}" for x, y in poly)
        lines.append(
            f'  <path d="{d}" fill="none" stroke="#555555" '
            f'stroke-width="{stroke_w:.3f}"/>\n'
        )
    for _, _, poly in rendered_edges:
        for x, y in poly[1:-1]:
            lines.append(
                f'  <circle cx="{x:.3f}" cy="{y:.3f}" r="{dot_r:.3f}" '
                f'fill="#e74c3c" stroke="none"/>\n'
            )
    # Node circles in pixel space too.
    for n, attrs in G.nodes(data=True):
        nx_, ny_ = tx(attrs["x"], attrs["y"])
        lines.append(
            f'  <circle cx="{nx_:.3f}" cy="{ny_:.3f}" r="{r:.3f}" '
            f'fill="#ffffff" stroke="#000000" '
            f'stroke-width="{r * 0.25:.3f}"/>\n'
        )
    lines.append("</svg>\n")
    path.write_text("".join(lines), encoding="utf-8")


def _render_original_with_display_transform(
    G: nx.Graph, path: Path, scale_label: str,
) -> None:
    """Render the original (curve) path at the native graph scale, but with
    pixel-range coordinates in the SVG so browser precision stays clean.
    Rewrites the `d` attribute by pulling each numeric literal through the
    display transform.
    """
    import re
    box = _layout(G)
    s, ox, oy = _display_transform(G)
    disp_w = box["width"] * s
    disp_h = box["height"] * s
    r = 0.012 * max(disp_w, disp_h)
    stroke_w = r * 0.4

    import svgpathtools

    def rewrite_path(d_str: str) -> str:
        """Parse the SVG path, apply (scale, translate) to every control
        point and endpoint, re-emit. Avoids the string-level pitfalls of
        mixed scientific-notation coords."""
        p = svgpathtools.parse_path(d_str)
        xform = complex(ox, oy)
        for seg in p:
            for attr in ("start", "control", "control1", "control2", "end"):
                if hasattr(seg, attr):
                    v = getattr(seg, attr)
                    setattr(seg, attr, complex(v.real * s + ox, v.imag * s + oy))
        return p.d()

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>\n',
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
        f'width="{disp_w:.3f}" height="{disp_h:.3f}" '
        f'viewBox="0 0 {disp_w:.3f} {disp_h:.3f}">\n',
    ]
    fs = disp_h * 0.045
    lines.append(
        f'  <text x="10" y="{fs * 1.3:.2f}" font-family="monospace" '
        f'font-size="{fs:.2f}" fill="#999999">'
        f'ORIGINAL — scale={scale_label}</text>\n'
    )
    for _, _, attrs in G.edges(data=True):
        d = rewrite_path(attrs["path"])
        lines.append(
            f'  <path d="{d}" fill="none" stroke="#1f77b4" '
            f'stroke-width="{stroke_w:.3f}"/>\n'
        )
    for n, attrs in G.nodes(data=True):
        nx_ = attrs["x"] * s + ox
        ny_ = attrs["y"] * s + oy
        lines.append(
            f'  <circle cx="{nx_:.3f}" cy="{ny_:.3f}" r="{r:.3f}" '
            f'fill="#ffffff" stroke="#000000" '
            f'stroke-width="{r * 0.25:.3f}"/>\n'
        )
    lines.append("</svg>\n")
    path.write_text("".join(lines), encoding="utf-8")


def _render_sampled_at_canvas(
    G: nx.Graph, path: Path, flatness_tol: float,
    canvas_width: float, caption: str,
) -> None:
    """Render the sampled polyline to an SVG whose width/height attributes
    are exactly `canvas_width` pixels (height scales with aspect ratio).
    Node radius, stroke width, and dot size are all computed in pixel
    space so proportions stay consistent across the sweep — the only
    thing that changes between sizes is the physical render size."""
    s, ox, oy, disp_w, disp_h = _display_transform_to(G, canvas_width)

    def tx(x, y):
        return x * s + ox, y * s + oy

    r = 0.012 * max(disp_w, disp_h)
    stroke_w = r * 0.4
    dot_r = r * 0.35

    svg_open = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
        f'width="{disp_w:.3f}" height="{disp_h:.3f}" '
        f'viewBox="0 0 {disp_w:.3f} {disp_h:.3f}">\n'
    )
    lines = [svg_open]

    total_samples = 0
    rendered_edges = []
    for u, v, attrs in G.edges(data=True):
        poly = edge_polyline(
            source=(G.nodes[u]["x"], G.nodes[u]["y"]),
            target=(G.nodes[v]["x"], G.nodes[v]["y"]),
            path_str=attrs["path"],
            flatness_tol=flatness_tol,
        )
        total_samples += len(poly)
        rendered_edges.append((u, v, [tx(x, y) for x, y in poly]))

    fs = disp_h * 0.045
    lines.append(
        f'  <text x="10" y="{fs * 1.3:.2f}" font-family="monospace" '
        f'font-size="{fs:.2f}" fill="#555555">{caption}</text>\n'
    )

    for _, _, poly in rendered_edges:
        d = "M" + " L".join(f"{x:.3f},{y:.3f}" for x, y in poly)
        lines.append(
            f'  <path d="{d}" fill="none" stroke="#555555" '
            f'stroke-width="{stroke_w:.3f}"/>\n'
        )
    for _, _, poly in rendered_edges:
        for x, y in poly[1:-1]:
            lines.append(
                f'  <circle cx="{x:.3f}" cy="{y:.3f}" r="{dot_r:.3f}" '
                f'fill="#e74c3c" stroke="none"/>\n'
            )
    for n, attrs in G.nodes(data=True):
        nx_, ny_ = tx(attrs["x"], attrs["y"])
        lines.append(
            f'  <circle cx="{nx_:.3f}" cy="{ny_:.3f}" r="{r:.3f}" '
            f'fill="#ffffff" stroke="#000000" '
            f'stroke-width="{r * 0.25:.3f}"/>\n'
        )
    lines.append("</svg>\n")
    path.write_text("".join(lines), encoding="utf-8")


def _render_original_at_canvas(
    G: nx.Graph, path: Path, canvas_width: float, caption: str,
) -> None:
    """Render the true SVG path at the given pixel canvas width."""
    import svgpathtools

    s, ox, oy, disp_w, disp_h = _display_transform_to(G, canvas_width)
    r = 0.012 * max(disp_w, disp_h)
    stroke_w = r * 0.4

    def rewrite_path(d_str: str) -> str:
        p = svgpathtools.parse_path(d_str)
        for seg in p:
            for attr in ("start", "control", "control1", "control2", "end"):
                if hasattr(seg, attr):
                    v = getattr(seg, attr)
                    setattr(seg, attr, complex(v.real * s + ox, v.imag * s + oy))
        return p.d()

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>\n',
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
        f'width="{disp_w:.3f}" height="{disp_h:.3f}" '
        f'viewBox="0 0 {disp_w:.3f} {disp_h:.3f}">\n',
    ]
    fs = disp_h * 0.045
    lines.append(
        f'  <text x="10" y="{fs * 1.3:.2f}" font-family="monospace" '
        f'font-size="{fs:.2f}" fill="#999999">{caption}</text>\n'
    )
    for _, _, attrs in G.edges(data=True):
        d = rewrite_path(attrs["path"])
        lines.append(
            f'  <path d="{d}" fill="none" stroke="#1f77b4" '
            f'stroke-width="{stroke_w:.3f}"/>\n'
        )
    for n, attrs in G.nodes(data=True):
        nx_ = attrs["x"] * s + ox
        ny_ = attrs["y"] * s + oy
        lines.append(
            f'  <circle cx="{nx_:.3f}" cy="{ny_:.3f}" r="{r:.3f}" '
            f'fill="#ffffff" stroke="#000000" '
            f'stroke-width="{r * 0.25:.3f}"/>\n'
        )
    lines.append("</svg>\n")
    path.write_text("".join(lines), encoding="utf-8")


def generate_canvas_sweep() -> None:
    """Render the signature drawing at a range of pixel canvas widths
    (300 .. 3000 px) — same geometry, same adaptive sampling, just
    different physical render sizes. Manual-inspection test: at higher
    magnification the polyline should still look smooth (no visible
    kinks) because the adaptive sampler's flatness tolerance is relative
    to the graph-coord diagonal, not to pixels.
    """
    sweep_dir = OUT_DIR / "canvas_sweep"
    sweep_dir.mkdir(exist_ok=True)
    widths = [300, 600, 1200, 2400, 3000]
    G = build_signature()
    tol = _flatness_tol(G)
    print("  canvas_sweep/ ...")
    for w in widths:
        # Total samples is independent of canvas size; compute once.
        poly_pts = sum(
            len(edge_polyline(
                source=(G.nodes[u]["x"], G.nodes[u]["y"]),
                target=(G.nodes[v]["x"], G.nodes[v]["y"]),
                path_str=attrs["path"],
                flatness_tol=tol,
            ))
            for u, v, attrs in G.edges(data=True)
        )
        cap_o = f"ORIGINAL — canvas {w}px"
        cap_s = f"SAMPLED — canvas {w}px  ({poly_pts} pts, tol={FLATNESS_FRACTION})"
        _render_original_at_canvas(
            G, sweep_dir / f"signature_canvas_{w}_original.svg", w, cap_o,
        )
        _render_sampled_at_canvas(
            G, sweep_dir / f"signature_canvas_{w}_sampled.svg", tol, w, cap_s,
        )
        print(f"    canvas={w:5d}px  samples={poly_pts}")


def generate_scale_sweep() -> None:
    """Render the signature drawing at several coordinate scales to a
    `scale_sweep/` sub-directory. Because both the SVG layout and the
    flatness_fraction parameter are scale-proportional, every sampled
    SVG should be visually identical (modulo the header text showing
    the actual coordinate range), with identical sample counts and
    metric values. Visual diff = scale-invariance proof.
    """
    sweep_dir = OUT_DIR / "scale_sweep"
    sweep_dir.mkdir(exist_ok=True)
    scales = [
        ("1e-3", 1e-3),
        ("1",    1.0),
        ("1e3",  1e3),
        ("1e6",  1e6),
    ]
    print("  scale_sweep/ ...")
    for label, k in scales:
        G = _scale_signature(k)
        tol = _flatness_tol(G)
        _render_original_with_display_transform(
            G, sweep_dir / f"signature_scale_{label}_original.svg", label,
        )
        _render_sampled_with_metrics(
            G, sweep_dir / f"signature_scale_{label}_sampled.svg",
            tol, label,
        )
        print(f"    scale={label:5s}  node_diag={math.hypot(*_layout_span(G)):.3e}  tol={tol:.3e}")


def _layout_span(G: nx.Graph) -> tuple:
    xs = [d["x"] for _, d in G.nodes(data=True)]
    ys = [d["y"] for _, d in G.nodes(data=True)]
    return (max(xs) - min(xs), max(ys) - min(ys))


def main() -> None:
    for name, builder in DRAWINGS.items():
        G = builder()
        tol = _flatness_tol(G)
        render_original(G, OUT_DIR / f"{name}_original.svg")
        render_sampled(G, OUT_DIR / f"{name}_sampled.svg", tol)
        print(f"  {name:14s}  tol={tol:.3f}")
    generate_scale_sweep()
    generate_canvas_sweep()
    print(
        f"Wrote {2 * len(DRAWINGS)} top-level SVGs + 8 scale_sweep SVGs + "
        f"10 canvas_sweep SVGs to {OUT_DIR}"
    )


if __name__ == "__main__":
    main()
