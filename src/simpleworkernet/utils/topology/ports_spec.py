# simpleworkernet/utils/topology/ports_spec.py
"""Единый параметр port — число, диапазон, список, строка."""
from __future__ import annotations
from typing import Any, Iterable, List, Optional, Set, Tuple, Union

# port=5
# port=(1, 8)
# port=[1, 2, (5, 8), 10]
# port=[5]
# port="1-8,10,12-15"
PortSpec = Union[
    None,
    int,
    str,
    Tuple[int, int],
    List[Any],
    Set[int],
]


def expand_ports(port: PortSpec = None) -> Optional[Set[int]]:
    """Разобрать port → множество номеров или None (= все порты).

    Форматы::

        expand_ports(5)                    # {5}
        expand_ports((1, 8))               # {1..8}
        expand_ports([1, 2, (5, 8), 10])   # {1,2,5,6,7,8,10}
        expand_ports([5])                  # {5}
        expand_ports("1-8,10,12-15")        # {1..8,10,12..15}
        expand_ports(None)                 # None — без ограничения
    """
    if port is None:
        return None

    result: Set[int] = set()

    if isinstance(port, bool):
        # bool is subclass of int — не принимаем
        raise TypeError(f"port: неверный тип {type(port)!r}")

    if isinstance(port, int):
        result.add(int(port))
        return result

    if isinstance(port, str):
        return _parse_ports_string(port)

    if isinstance(port, tuple):
        result |= _item_to_ports(port)
        return result

    if isinstance(port, (list, set, frozenset)):
        if len(port) == 0:
            return None
        for item in port:
            result |= _item_to_ports(item)
        return result

    # одиночное значение, приводимое к int (например numpy.int64)
    try:
        result.add(int(port))
        return result
    except (TypeError, ValueError):
        raise TypeError(
            f"port: неподдерживаемый формат {port!r} (type={type(port).__name__})"
        )


def _item_to_ports(item: Any) -> Set[int]:
    """Один элемент списка/кортежа → множество портов."""
    if isinstance(item, bool):
        raise TypeError(f"port: неверный элемент {item!r}")
    if isinstance(item, int):
        return {int(item)}
    if isinstance(item, str):
        return _parse_ports_string(item)
    if isinstance(item, tuple):
        if len(item) != 2:
            raise TypeError(
                f"port: диапазон должен быть кортежем из 2 int, получено {item!r}"
            )
        a, b = int(item[0]), int(item[1])
        return set(range(min(a, b), max(a, b) + 1))
    if isinstance(item, list):
        # вложенный список — разворачиваем
        out: Set[int] = set()
        for x in item:
            out |= _item_to_ports(x)
        return out
    try:
        return {int(item)}
    except (TypeError, ValueError):
        raise TypeError(f"port: неподдерживаемый элемент {item!r}")


def _parse_ports_string(s: str) -> Set[int]:
    out: Set[int] = set()
    for part in s.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            lo, hi = int(a.strip()), int(b.strip())
            out |= set(range(min(lo, hi), max(lo, hi) + 1))
        else:
            out.add(int(part))
    return out


def filter_ports(available: Iterable[int], allowed: Optional[Set[int]]) -> List[int]:
    if allowed is None:
        return sorted(set(int(p) for p in available))
    return sorted(p for p in set(int(x) for x in available) if p in allowed)
