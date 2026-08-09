# simpleworkernet/utils/topology/graphs/__init__.py
from .cgraph import CGraph
from .fngraph import FNGraph
from .cgraph_extra import cgraph_is_linear

# подмешиваем is_linear без раздувания cgraph.py
if not hasattr(CGraph, "is_linear"):
    CGraph.is_linear = cgraph_is_linear  # type: ignore[attr-defined]

__all__ = ["CGraph", "FNGraph"]
