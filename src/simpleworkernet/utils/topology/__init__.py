# simpleworkernet/utils/topology/__init__.py
"""Модульная графовая топология сети WorkerNet."""

from .constants import (
    TYPE_CUSTOMER, TYPE_FIBER, TYPE_SPLITTER, TYPE_CROSS, TYPE_CWDM,
    TYPE_SWITCH, TYPE_OLT, TYPE_ONU, TYPE_RADIO,
    DEVICE_TYPES, SIDE_TYPES, TERMINAL_TYPES, ALL_OBJECT_TYPES,
)
from .errors import TopologyBuildError
from .keys import ObjKey, Interface
from .models import CGraphVertex, CGraphEdge, FNGraphVertex, FNGraphEdge
from .cache import DataCache
from .graphs import CGraph, FNGraph
from .topology import NetworkTopology
from .merge import merge_cgraphs, merge_fngraphs
from .attenuation import (
    Attenuation, AttenuationCatalog, AttenuationSegment, PathReport, MultiPathReport,
)

__all__ = [
    "TYPE_CUSTOMER", "TYPE_FIBER", "TYPE_SPLITTER", "TYPE_CROSS", "TYPE_CWDM",
    "TYPE_SWITCH", "TYPE_OLT", "TYPE_ONU", "TYPE_RADIO",
    "DEVICE_TYPES", "SIDE_TYPES", "TERMINAL_TYPES", "ALL_OBJECT_TYPES",
    "TopologyBuildError",
    "ObjKey", "Interface",
    "CGraphVertex", "CGraphEdge", "FNGraphVertex", "FNGraphEdge",
    "DataCache", "CGraph", "FNGraph",
    "merge_cgraphs", "merge_fngraphs",
    "NetworkTopology",
    "Attenuation", "AttenuationCatalog", "AttenuationSegment",
    "PathReport", "MultiPathReport",
]
