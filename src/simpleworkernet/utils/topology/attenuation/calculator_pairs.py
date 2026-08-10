# simpleworkernet/utils/topology/attenuation/calculator_pairs.py
"""Стратегии построения CGraph для пар object1–object2."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Set

from ...constants import (
    TYPE_FIBER,
    TYPE_CROSS,
    TYPE_SPLITTER,
    TYPE_CWDM,
    TYPE_OLT,
    TYPE_SWITCH,
    TYPE_CUSTOMER,
    TYPE_ONU,
    TYPE_RADIO,
    ALL_OBJECT_TYPES,
)
from .errors import AttenuationError

KNOWN: Set[str] = set(ALL_OBJECT_TYPES)

# типы, для которых side/port обычно не обязательны
_NO_SIDE_TYPES = frozenset({
    TYPE_CUSTOMER, TYPE_OLT, TYPE_SWITCH, TYPE_ONU, TYPE_RADIO,
})


@dataclass(frozen=True)
class PairPlan:
    """План построения для пары объектов."""
    strategy: str  # fn_corridor | from_a | from_b | from_either | merge | from_single
    require_side_a: bool = False
    require_side_b: bool = False
    require_port_a: bool = False
    require_port_b: bool = False
    require_port_either: bool = False
    notes: str = ""


def _norm(t: str) -> str:
    return (t or "").strip().lower()


def pair_plan(type_a: str, type_b: Optional[str] = None) -> PairPlan:
    """План построения для пары типов (type_b=None — только от type_a)."""
    a = _norm(type_a)
    if a not in KNOWN:
        raise AttenuationError(f"неизвестный тип obj1: {type_a!r}")

    if not type_b:
        # одиночный старт: строим от A, ищем терминалы в графе
        if a == TYPE_FIBER:
            return PairPlan(
                strategy="from_a",
                require_side_a=False,
                require_port_a=True,
                notes="только fiber: нужен port (номер ОВ); side желателен",
            )
        return PairPlan(
            strategy="from_a",
            notes=f"только {a}: build от объекта, цели — OLT/switch/… в графе",
        )

    b = _norm(type_b)
    if b not in KNOWN:
        raise AttenuationError(f"неизвестный тип obj2: {type_b!r}")

    if a == TYPE_FIBER and b == TYPE_FIBER:
        return PairPlan(
            strategy="fn_corridor",
            require_side_a=False,
            require_side_b=False,
            require_port_either=True,
            notes="fiber↔fiber: port хотя бы у одного; side желателен",
        )

    if a == TYPE_OLT and b == TYPE_CUSTOMER:
        return PairPlan(strategy="from_a", notes="от OLT к абоненту")
    if a == TYPE_CUSTOMER and b in (TYPE_OLT, TYPE_SWITCH):
        return PairPlan(strategy="from_b", notes="от устройства к абоненту")
    if a in (TYPE_SPLITTER, TYPE_CWDM) and b == TYPE_CUSTOMER:
        return PairPlan(strategy="from_a", notes="от сплиттера/CWDM к абоненту")
    if a == TYPE_CUSTOMER and b in (TYPE_SPLITTER, TYPE_CWDM):
        return PairPlan(strategy="from_b", notes="от сплиттера/CWDM к абоненту")
    if a == TYPE_CROSS or b == TYPE_CROSS:
        return PairPlan(strategy="from_either", notes="кросс: id=uuid; port желателен")
    if a in (TYPE_SPLITTER, TYPE_CWDM) or b in (TYPE_SPLITTER, TYPE_CWDM):
        return PairPlan(
            strategy="from_either",
            notes="сплиттер/CWDM: port желателен для точного порта",
        )
    return PairPlan(
        strategy="from_either",
        notes="общий случай: build от A или B, при необходимости merge",
    )


def validate_pair_inputs(
    type_a, id_a, side_a, port_a,
    type_b=None, id_b=None, side_b=None, port_b=None,
) -> PairPlan:
    """Проверить входы; вернуть PairPlan или AttenuationError.

    obj2 / side / port необязательны, если по типу можно однозначно построить
    (customer, olt, …). Для fiber↔fiber по-прежнему нужен port хотя бы с одной стороны.
    """
    if not type_a:
        raise AttenuationError("obj1_type не задан")
    if id_a is None or id_a == "":
        raise AttenuationError("obj1_id не задан")

    has_b = type_b is not None and id_b is not None and id_b != ""
    if type_b and not has_b:
        raise AttenuationError("obj2_type задан, но obj2_id пуст")
    if has_b and not type_b:
        raise AttenuationError("obj2_id задан, но obj2_type пуст")

    plan = pair_plan(type_a, type_b if has_b else None)

    # side обязателен только если план явно требует и тип «сторонний»
    if plan.require_side_a and side_a is None and _norm(type_a) not in _NO_SIDE_TYPES:
        raise AttenuationError(
            f"для {type_a} (obj1) укажите side (1|2) — сторону сооружения"
        )
    if has_b and plan.require_side_b and side_b is None and _norm(type_b) not in _NO_SIDE_TYPES:
        raise AttenuationError(
            f"для {type_b} (obj2) укажите side (1|2) — сторону сооружения"
        )

    if plan.require_port_a and port_a is None:
        raise AttenuationError(
            f"для {type_a} (obj1) укажите port "
            f"({'номер ОВ' if _norm(type_a) == TYPE_FIBER else 'порт/интерфейс'})"
        )
    if has_b and plan.require_port_b and port_b is None:
        raise AttenuationError(
            f"для {type_b} (obj2) укажите port "
            f"({'номер ОВ' if _norm(type_b) == TYPE_FIBER else 'порт/интерфейс'})"
        )
    if plan.require_port_either and port_a is None and port_b is None:
        raise AttenuationError(
            f"для {_norm(type_a)}↔{_norm(type_b or '')} укажите port хотя бы у одного конца"
        )
    return plan
