"""Тесты strategy-handlers."""

from simpleworkernet.utils.topology.builders.handlers import (
    CrossHandler,
    FiberHandler,
    TerminalHandler,
    get_handler,
)
from simpleworkernet.utils.topology.builders.handlers_splitter import SplitterCwdmHandler
from simpleworkernet.utils.topology.constants import (
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


def test_get_handler_terminal():
    for t in (TYPE_OLT, TYPE_SWITCH, TYPE_ONU, TYPE_RADIO, TYPE_CUSTOMER):
        assert isinstance(get_handler(t), TerminalHandler)


def test_get_handler_side():
    assert isinstance(get_handler(TYPE_CROSS), CrossHandler)
    assert isinstance(get_handler(TYPE_FIBER), FiberHandler)
    assert isinstance(get_handler(TYPE_SPLITTER), SplitterCwdmHandler)
    assert isinstance(get_handler(TYPE_CWDM), SplitterCwdmHandler)


def test_get_handler_unknown():
    try:
        get_handler("unknown_type")
        assert False, "expected ValueError"
    except ValueError as e:
        assert "unknown_type" in str(e)
