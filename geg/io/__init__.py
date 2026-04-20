"""I/O subpackage: readers, writers, and format converters.

Public entry points are re-exported from the top-level `geg` package, so
callers should continue to write:

    from geg import read_geg, write_geg, graphml_to_geg, gml_to_geg

This module organises them internally by format.
"""

from .geg import (
    read_geg,
    write_geg,
    has_self_loops_file,
    is_multigraph_file,
)
from .graphml import (
    read_graphml,
    write_graphml,
    graphml_to_geg,
    convert_gml_to_graphml,
    convert_graphml_to_gml,
)
from .gml import gml_to_geg

__all__ = [
    "read_geg",
    "write_geg",
    "has_self_loops_file",
    "is_multigraph_file",
    "read_graphml",
    "write_graphml",
    "graphml_to_geg",
    "convert_gml_to_graphml",
    "convert_graphml_to_gml",
    "gml_to_geg",
]
