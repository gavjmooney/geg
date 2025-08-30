from . import geg_parser
import networkx as nx

def aspect_ratio(G: nx.Graph) -> float:
    """
    Compute the aspect ratio of the drawing's bounding box.

    The aspect ratio is defined as min(width/height, height/width), yielding a
    value in (0, 1], where 1 represents a square bounding box and smaller
    values indicate more elongated drawings. The bounding box is computed using
    `geg.get_bounding_box`, which accounts for curve promotion to avoid cutting
    off curved edges.

    Args:
        G: A NetworkX graph with node coordinates 'x' and 'y'.

    Returns:
        A float in [0, 1], or 0.0 if width or height is non-positive.
    """
    # Get width and height of bounding box
    min_x, min_y, max_x, max_y = geg_parser.get_bounding_box(G) # geg handles curve promotion
    w, h = max_x - min_x, max_y - min_y
    if w <= 0 or h <= 0:
        return 0.0
    
    return min(w/h, h/w)
