import networkx as nx

from . import geg_parser


def aspect_ratio(G: nx.Graph) -> float:
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

    Returns:
        Float in [0, 1], 1 = square bounding box (or degenerate 1D/0D drawing).
    """
    min_x, min_y, max_x, max_y = geg_parser.get_bounding_box(G)
    w, h = max_x - min_x, max_y - min_y
    if w == 0 or h == 0:
        return 1.0
    return h / w if h <= w else w / h
