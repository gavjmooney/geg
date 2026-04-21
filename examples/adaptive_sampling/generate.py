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


DRAWINGS: Dict[str, Callable[[], nx.Graph]] = {
    "sine_wave":    build_sine_wave,
    "flower":       build_flower,
    "pinwheel":     build_pinwheel,
    "tangled_s":    build_tangled_s,
    "flow_network": build_flow_network,
    "signature":    build_signature,
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


def _render_sampled_with_metrics(
    G: nx.Graph, path: Path, flatness_tol: float, scale_label: str,
) -> None:
    """Variant of render_sampled that overlays sample count + metric
    values + the scale label in the header text, for side-by-side
    scale-sweep comparison."""
    from geg import edge_crossings, edge_orthogonality, node_edge_occlusion

    box = _layout(G)
    r = _node_radius(box)
    stroke_w = r * 0.4
    dot_r = r * 0.35
    lines = [_svg_open(box)]
    diag = math.hypot(box["width"], box["height"])

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
        rendered_edges.append((u, v, poly))

    eo = edge_orthogonality(G, flatness_fraction=FLATNESS_FRACTION)
    ec = edge_crossings(G, flatness_fraction=FLATNESS_FRACTION)
    neo = node_edge_occlusion(G, flatness_fraction=FLATNESS_FRACTION)

    fs = diag * 0.018
    # Multiple header lines so the readout stays legible.
    lines.append(
        f'  <text x="{box["min_x"] + 10}" y="{box["min_y"] + fs * 1.3}" '
        f'font-family="monospace" font-size="{fs:.2f}" fill="#555555">'
        f'scale={scale_label}  {total_samples} pts</text>\n'
    )
    lines.append(
        f'  <text x="{box["min_x"] + 10}" y="{box["min_y"] + fs * 2.7}" '
        f'font-family="monospace" font-size="{fs * 0.75:.2f}" fill="#999999">'
        f'EO={eo:.6f}  EC={ec:.6f}  NEO={neo:.6f}</text>\n'
    )

    for u, v, poly in rendered_edges:
        # `%g` preserves full float precision without scale-dependent
        # decimal truncation (a %.3f would round 0.0375 to 0.038 at
        # scale 1e-3 while printing 37.5 exactly at scale 1).
        d = "M" + " L".join(f"{x:.10g},{y:.10g}" for x, y in poly)
        lines.append(
            f'  <path d="{d}" fill="none" stroke="#555555" '
            f'stroke-width="{stroke_w:g}"/>\n'
        )
    for _, _, poly in rendered_edges:
        for x, y in poly[1:-1]:
            lines.append(
                f'  <circle cx="{x:.10g}" cy="{y:.10g}" r="{dot_r:.10g}" '
                f'fill="#e74c3c" stroke="none"/>\n'
            )
    lines.append(_render_nodes(G, r))
    lines.append("</svg>\n")
    path.write_text("".join(lines), encoding="utf-8")


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
        render_original(G, sweep_dir / f"signature_scale_{label}_original.svg")
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
    print(f"Wrote {2 * len(DRAWINGS)} top-level SVGs + 8 scale_sweep SVGs to {OUT_DIR}")


if __name__ == "__main__":
    main()
