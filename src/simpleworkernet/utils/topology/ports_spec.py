# simpleworkernet/utils/topology/ports_spec.py
"""Нормализация спецификации портов: число, список, диапазоны, строка."""
from __future__ import annotations
from typing import Iterable, List, Optional, Set, Tuple, Union

PortSpec = Union[None, int, str, List[int], Set[int], Tuple[int, int], List[Tuple[int, int]]]


def expand_ports(
    port: Optional[int] = None,
    ports: PortSpec = None,
    port_ranges: Optional[Union[Tuple[int, int], List[Tuple[int, int]]]] = None,
) -> Optional[Set[int]]:
    """Множество портов или None (= все).

    expand_ports(port=5)
    expand_ports(ports=[1,2,3])
    expand_ports(ports="1-8,10,12-15")
    expand_ports(port_ranges=[(1,8),(10,12)])
    """
    result: Set[int] = set()
    has_explicit = False
    if port is not None:
        result.add(int(port))
        has_explicit = True
    if ports is not None:
        has_explicit = True
        if isinstance(ports, int):
            result.add(int(ports))
        elif isinstance(ports, str):
            result |= _parse_ports_string(ports)
        elif isinstance(ports, tuple) and len(ports) == 2 and all(
            isinstance(x, int) for x in ports
        ):
            a, b = int(ports[0]), int(ports[1])
            result |= set(range(min(a, b), max(a, b) + 1))
        else:
            for item in ports:  # type: ignore[union-attr]
                if isinstance(item, tuple) and len(item) == 2:
                    a, b = int(item[0]), int(item[1])
                    result |= set(range(min(a, b), max(a, b) + 1))
                else:
                    result.add(int(item))
    if port_ranges is not None:
        has_explicit = True
        ranges = port_ranges if isinstance(port_ranges, list) else [port_ranges]
        for a, b in ranges:
            a, b = int(a), int(b)
            result |= set(range(min(a, b), max(a, b) + 1))
    if not has_explicit:
        return None
    return result


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
