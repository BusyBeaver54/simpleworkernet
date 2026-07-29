# simpleworkernet/utils/graph.py
"""
DEPRECATED: используйте simpleworkernet.utils.topology

Совместимость: реэкспорт из нового пакета topology.
Старый монолитный файл будет удалён в следующем мажорном релизе.
"""

import warnings

warnings.warn(
    "simpleworkernet.utils.graph is deprecated; "
    "use simpleworkernet.utils.topology instead",
    DeprecationWarning,
    stacklevel=2,
)

from .topology import (  # noqa: E402, F401
    CGraph,
    FNGraph,
    DataCache,
    ObjKey,
    Interface,
    CGraphVertex,
    CGraphEdge,
    FNGraphVertex,
    FNGraphEdge,
    TYPE_CUSTOMER,
    TYPE_FIBER,
    TYPE_SPLITTER,
    TYPE_CROSS,
    TYPE_CWDM,
    TYPE_SWITCH,
    TYPE_OLT,
    TYPE_ONU,
    DEVICE_TYPES,
    SIDE_TYPES,
    TERMINAL_TYPES,
)

__all__ = [
    "CGraph",
    "FNGraph",
    "DataCache",
    "ObjKey",
    "Interface",
    "CGraphVertex",
    "CGraphEdge",
    "FNGraphVertex",
    "FNGraphEdge",
    "TYPE_CUSTOMER",
    "TYPE_FIBER",
    "TYPE_SPLITTER",
    "TYPE_CROSS",
    "TYPE_CWDM",
    "TYPE_SWITCH",
    "TYPE_OLT",
    "TYPE_ONU",
    "DEVICE_TYPES",
    "SIDE_TYPES",
    "TERMINAL_TYPES",
]
