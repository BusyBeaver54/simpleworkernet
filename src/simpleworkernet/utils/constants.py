# simpleworkernet/utils/constants.py
"""Общие константы типов объектов сети WorkerNet.

Единый источник для topology, attenuation и прочих утилит::

    from simpleworkernet.utils.constants import TYPE_FIBER, TYPE_OLT
    from simpleworkernet.utils import TYPE_FIBER  # реэкспорт
"""

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

ALL_OBJECT_TYPES: Set[str] = SIDE_TYPES | TERMINAL_TYPES
