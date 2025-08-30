from .geg_parser import (
    read_geg, write_geg, gml_to_geg, graphml_to_geg,
    get_bounding_box, to_svg, euclidean_distance,
    contains_polylines, contains_curves, contains_straight_bends,
    has_self_loops_file, has_self_loops_graph,
    is_multigraph_file, is_multigraph_graph,
    curves_promotion, approximate_edge_polyline,
    compute_global_scale, determine_N_for_segment,
    get_convex_hull_area,
)

from .aspect_ratio import aspect_ratio
from .angular_resolution import angular_resolution_min_angle, angular_resolution_avg_angle
from .crossing_angle import crossing_angle
from .edge_crossings import edge_crossings, edge_crossings_bezier
from .edge_length_deviation import edge_length_deviation
from .edge_orthogonality import edge_orthogonality, curved_edge_orthogonality
from .gabriel_ratio import gabriel_ratio_edges, gabriel_ratio_nodes
from .kruskal_stress import kruskal_stress
from .neighbourhood_preservation import neighbourhood_preservation
from .node_resolution import node_resolution
from .node_uniformity import node_uniformity

__all__ = [
    # parser/core
    "read_geg","write_geg","gml_to_geg","graphml_to_geg",
    "get_bounding_box","to_svg","euclidean_distance",
    "contains_polylines","contains_curves","contains_straight_bends",
    "has_self_loops_file","has_self_loops_graph",
    "is_multigraph_file","is_multigraph_graph",
    "curves_promotion","approximate_edge_polyline",
    "compute_global_scale","determine_N_for_segment",
    "get_convex_hull_area",
    # metrics
    "aspect_ratio","angular_resolution_min_angle","angular_resolution_avg_angle",
    "crossing_angle","edge_crossings","edge_crossings_bezier",
    "edge_length_deviation","edge_orthogonality","curved_edge_orthogonality",
    "gabriel_ratio_edges","gabriel_ratio_nodes","kruskal_stress",
    "neighbourhood_preservation","node_resolution","node_uniformity",
]