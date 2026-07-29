# simpleworkernet/utils/topology/__init__.py
"""
Модульная графовая топология сети WorkerNet.

Публичный API:
    Topology, CGraph, FNGraph, DataCache, ObjKey, Interface,
    CGraphVertex, CGraphEdge, FNGraphVertex, FNGraphEdge,
    константы типов объектов.
"""

from .constants import (
    TYPE_CUSTOMER,
    TYPE_FIBER,
    TYPE_SPLITTER,
    TYPE_CROSS,
    TYPE_CWDM,
    TYPE_SWITCH,
    TYPE_OLT,
    TYPE_ONU,
    TYPE_RADIO,
    DEVICE_TYPES,
    SIDE_TYPES,
    TERMINAL_TYPES,
)
from .keys import ObjKey, Interface
from .models import CGraphVertex, CGraphEdge, FNGraphVertex, FNGraphEdge
from .cache import DataCache
from .graphs import CGraph, FNGraph
from .topology import Topology
from .merge import merge_cgraphs, merge_fngraphs

__all__ = [
    # constants
    "TYPE_CUSTOMER",
    "TYPE_FIBER",
    "TYPE_SPLITTER",
    "TYPE_CROSS",
    "TYPE_CWDM",
    "TYPE_SWITCH",
    "TYPE_OLT",
    "TYPE_ONU",
    "TYPE_RADIO",
    "DEVICE_TYPES",
    "SIDE_TYPES",
    "TERMINAL_TYPES",
    # keys
    "ObjKey",
    "Interface",
    # models
    "CGraphVertex",
    "CGraphEdge",
    "FNGraphVertex",
    "FNGraphEdge",
    # cache
    "DataCache",
    # graphs
    "CGraph",
    "FNGraph",
    # merge
    "merge_cgraphs",
    "merge_fngraphs",
    # high-level
    "Topology",
]
