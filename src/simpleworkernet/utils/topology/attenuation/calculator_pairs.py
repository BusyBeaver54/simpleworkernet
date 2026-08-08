# simpleworkernet/utils/topology/attenuation/calculator_pairs.py
"""Стратегии построения CGraph для пар object1–object2."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Set

from ..constants import (
    TYPE_FIBER,
    TYPE_CROSS,
    TYPE_SPLITTER,
    TYPE_CWDM,
    TYPE_OLT,
    TYPE_SWITCH,
    TYPE_ONU,
    TYPE_RADIO,
    TYPE_CUSTOMER,
    ALL_OBJECT_TYPES,
)
from .errors import AttenuationError

KNOWN: Set[str] = set(ALL_OBJECT_TYPES)


@dataclass(frozen=True)
class PairPlan:
    """План построения для пары объектов."""
    strategy: str  # fn_corridor | from_a | from_b | from_either | merge
    require_side_a: bool = False
    require_side_b: bool = False
    require_port_a: bool = False
    require_port_b: bool = False
    require_port_either: bool = False
    notes: str = ""


def _norm(t: str) -> str:
    return (t or "").strip().lower()


def pair_plan(type_a: str, type_b: str) -> PairPlan:
    """План построения для пары типов."""
    a, b = _norm(type_a), _norm(type_b)
    if a not in KNOWN:
        raise AttenuationError(f"неизвестный тип obj1: {type_a!r}")
    if b not in KNOWN:
        raise AttenuationError(f"неизвестный тип obj2: {type_b!r}")

    if a == TYPE_FIBER and b == TYPE_FIBER:
        return PairPlan(
            strategy="fn_corridor",
            require_side_a=True,
            require_side_b=True,
            require_port_either=True,
            notes="FNGraph между сооружениями сторон → CGraph по ОВ коридора",
        )
    if a == TYPE_FIBER:
        return PairPlan(
            strategy="from_a",
            require_side_a=True,
            require_port_a=True,
            notes="старт от кабеля (side+ОВ), путь до второго объекта",
        )
    if b == TYPE_FIBER:
        return PairPlan(
            strategy="from_b",
            require_side_b=True,
            require_port_b=True,
            notes="старт от кабеля (side+ОВ) со стороны obj2",
        )
    if a in (TYPE_OLT, TYPE_SWITCH) and b == TYPE_CUSTOMER:
        return PairPlan(
            strategy="from_a",
            notes="от устройства к абоненту; port=GPON if желателен",
        )
    if a == TYPE_CUSTOMER and b in (TYPE_OLT, TYPE_SWITCH):
        return PairPlan(
            strategy="from_b",
            notes="от устройства к абоненту",
        )
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
    type_b, id_b, side_b, port_b,
) -> PairPlan:
    """Проверить входы; вернуть PairPlan или AttenuationError."""
    if not type_a:
        raise AttenuationError("obj1_type не задан")
    if not type_b:
        raise AttenuationError("obj2_type не задан")
    if id_a is None or id_a == "":
        raise AttenuationError("obj1_id не задан")
    if id_b is None or id_b == "":
        raise AttenuationError("obj2_id не задан")

    plan = pair_plan(type_a, type_b)

    if plan.require_side_a and side_a is None:
        raise AttenuationError(
            f"для {type_a} (obj1) укажите side (1|2) — сторону сооружения"
        )
    if plan.require_side_b and side_b is None:
        raise AttenuationError(
            f"для {type_b} (obj2) укажите side (1|2) — сторону сооружения"
        )
    if plan.require_port_a and port_a is None:
        raise AttenuationError(
            f"для {type_a} (obj1) укажите port "
            f"({'номер ОВ' if _norm(type_a) == TYPE_FIBER else 'порт/интерфейс'})"
        )
    if plan.require_port_b and port_b is None:
        raise AttenuationError(
            f"для {type_b} (obj2) укажите port "
            f"({'номер ОВ' if _norm(type_b) == TYPE_FIBER else 'порт/интерфейс'})"
        )
    if plan.require_port_either and port_a is None and port_b is None:
        raise AttenuationError(
            f"для {_norm(type_a)}↔{_norm(type_b)} укажите port хотя бы у одного конца"
        )
    return plan
