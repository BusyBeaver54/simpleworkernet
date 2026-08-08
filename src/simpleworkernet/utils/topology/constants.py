# simpleworkernet/utils/topology/constants.py
"""Константы типов объектов сети — единый источник для topology и attenuation."""

from typing import Set

TYPE_CUSTOMER = "customer"
TYPE_FIBER = "fiber"
TYPE_SPLITTER = "splitter"
TYPE_CROSS = "cross"
TYPE_CWDM = "cwdm"
TYPE_SWITCH = "switch"
TYPE_OLT = "olt"
TYPE_ONU = "onu"
TYPE_RADIO = "radio"

DEVICE_TYPES: Set[str] = {TYPE_SWITCH, TYPE_OLT, TYPE_ONU, TYPE_RADIO}
SIDE_TYPES: Set[str] = {TYPE_CROSS, TYPE_FIBER, TYPE_SPLITTER, TYPE_CWDM}
TERMINAL_TYPES: Set[str] = {TYPE_CUSTOMER} | DEVICE_TYPES

# все известные типы объектов графа / calculate()
ALL_OBJECT_TYPES: Set[str] = SIDE_TYPES | TERMINAL_TYPES
