from typing import Optional, Tuple

import networkx as nx

from . import geg_parser


def aspect_ratio(
    G: nx.Graph,
    *,
    bbox: Optional[Tuple[float, float, float, float]] = None,
) -> float:
    """Aspect-ratio metric in [0, 1].

    Paper §3.2:
        Asp(D) = 1             if h(D) = 0 or w(D) = 0
               = h(D) / w(D)   if h(D) <= w(D)
               = w(D) / h(D)   otherwise
    where h, w are the height and width of the axis-aligned bounding box of
    the drawing, computed with curve geometry promoted so that curved edges
    extend the box.

    Args:
        G: NetworkX graph with node attributes 'x', 'y' and optional edge
           'path' / 'polyline' attributes.
        bbox: Optional pre-computed (min_x, min_y, max_x, max_y). If None,
            computed via `geg_parser.get_bounding_box(G)`. Pass a cached
            bounding box when invoking several bbox-dependent metrics on the
            same graph to avoid re-running `curves_promotion`.

    Returns:
        Float in [0, 1], 1 = square bounding box (or degenerate 1D/0D drawing).
    """
    if bbox is None:
        bbox = geg_parser.get_bounding_box(G)
    min_x, min_y, max_x, max_y = bbox
    w, h = max_x - min_x, max_y - min_y
    if w == 0 or h == 0:
        return 1.0
    return h / w if h <= w else w / h
