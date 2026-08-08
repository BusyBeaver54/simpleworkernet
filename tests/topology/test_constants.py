"""Тесты констант типов."""

from simpleworkernet.utils.constants import (
    ALL_OBJECT_TYPES,
    DEVICE_TYPES,
    SIDE_TYPES,
    TERMINAL_TYPES,
    TYPE_CROSS,
    TYPE_CUSTOMER,
    TYPE_CWDM,
    TYPE_FIBER,
    TYPE_OLT,
    TYPE_ONU,
    TYPE_RADIO,
    TYPE_SPLITTER,
    TYPE_SWITCH,
)
# обратная совместимость реэкспорта
from simpleworkernet.utils.topology.constants import TYPE_FIBER as TYPE_FIBER_TOPO


def test_device_types():
    assert TYPE_OLT in DEVICE_TYPES
    assert TYPE_SWITCH in DEVICE_TYPES
    assert TYPE_ONU in DEVICE_TYPES
    assert TYPE_RADIO in DEVICE_TYPES
    assert TYPE_CUSTOMER not in DEVICE_TYPES


def test_side_types():
    assert TYPE_CROSS in SIDE_TYPES
    assert TYPE_FIBER in SIDE_TYPES
    assert TYPE_SPLITTER in SIDE_TYPES
    assert TYPE_CWDM in SIDE_TYPES
    assert TYPE_OLT not in SIDE_TYPES


def test_terminal_types():
    assert TYPE_CUSTOMER in TERMINAL_TYPES
    assert DEVICE_TYPES <= TERMINAL_TYPES


def test_all_object_types():
    assert TYPE_FIBER in ALL_OBJECT_TYPES
    assert TYPE_OLT in ALL_OBJECT_TYPES
    assert SIDE_TYPES | TERMINAL_TYPES == ALL_OBJECT_TYPES


def test_topology_reexport():
    assert TYPE_FIBER_TOPO == TYPE_FIBER
