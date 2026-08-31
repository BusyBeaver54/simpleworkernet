# simpleworkernet/utils/topology/constants.py
"""Реэкспорт типов объектов.

Источник истины: ``simpleworkernet.utils.constants``.
Этот модуль оставлен для обратной совместимости::

    from simpleworkernet.utils.topology.constants import TYPE_FIBER  # OK
    from simpleworkernet.utils.constants import TYPE_FIBER           # предпочтительно
"""

from ..constants import (  # noqa: F401
    TYPE_NODE,
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
    ALL_OBJECT_TYPES,
)

__all__ = [
    "TYPE_NODE",
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
    "ALL_OBJECT_TYPES",
]
